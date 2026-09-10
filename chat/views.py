import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q

from .models import Conversation, Message
from claims.models import OwnershipClaim, ReturnConfirmation
from matching.models import Match
from notifications.utils import notify_user
from claims.ai_verifier import (
    generate_ai_interview_question,
    evaluate_interview_transcript,
    TOTAL_VERIFICATION_STEPS,
)
from claims.emails import send_ai_verified_claim_email


def _serialize_message(msg, request_user=None):
    """Helper to serialize a Message for template & AJAX JSON responses."""
    is_me = bool(request_user and msg.sender == request_user)
    if msg.is_ai:
        sender_name = "FindX AI Officer"
        initial = "🤖"
        avatar_url = None
    elif msg.sender:
        sender_name = msg.sender.get_full_name_or_username()
        initial = msg.sender.username[:1].upper()
        avatar_url = msg.sender.avatar.url if msg.sender.avatar else None
    else:
        sender_name = "FindX System"
        initial = "🛡️"
        avatar_url = None

    local_time = timezone.localtime(msg.created_at).strftime("%I:%M %p").lstrip('0')

    return {
        'id': msg.id,
        'content': msg.content,
        'image_url': msg.image.url if msg.image else None,
        'message_type': msg.message_type,
        'is_ai': msg.is_ai,
        'sender': sender_name,
        'sender_id': msg.sender.id if msg.sender else None,
        'is_me': is_me,
        'avatar_url': avatar_url,
        'initial': initial,
        'created_at': local_time,
    }


@login_required
def conversation_list(request):
    convos = Conversation.objects.filter(
        Q(participant_a=request.user) | Q(participant_b=request.user)
    ).select_related(
        'participant_a', 'participant_b', 'match',
        'match__lost_item', 'match__found_item'
    ).order_by('-created_at')
    ctx = {'conversations': convos}
    return render(request, 'chat/conversation_list.html', ctx)


@login_required
def conversation_detail(request, pk):
    convo = get_object_or_404(Conversation, pk=pk)
    if request.user not in (convo.participant_a, convo.participant_b):
        messages.error(request, 'You do not have access to this conversation.')
        return redirect('core:dashboard')

    is_claimant = (request.user == convo.participant_a)
    is_finder   = (request.user == convo.participant_b)

    # Mark incoming messages as read (exclude own and system/AI)
    convo.messages.filter(is_read=False).exclude(sender=request.user).exclude(is_ai=True).update(is_read=True)

    msgs = convo.messages.select_related('sender').order_by('created_at')
    other = convo.other_participant(request.user)
    claim = convo.match.claims.filter(claimant=convo.participant_a).first()

    ctx = {
        'conversation': convo,
        'chat_messages': msgs,
        'other': other,
        'claim': claim,
        'is_claimant': is_claimant,
        'is_finder': is_finder,
        'is_closed': convo.is_closed,
        'total_steps': TOTAL_VERIFICATION_STEPS,
    }
    return render(request, 'chat/conversation_detail.html', ctx)


@login_required
@require_POST
def send_message(request, pk):
    convo = get_object_or_404(Conversation, pk=pk)
    if request.user not in (convo.participant_a, convo.participant_b):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if convo.is_closed:
        return JsonResponse({'error': 'This conversation is closed because the item has been returned.'}, status=400)

    is_claimant = (request.user == convo.participant_a)
    is_finder   = (request.user == convo.participant_b)

    content = request.POST.get('content', '').strip()
    image_file = request.FILES.get('image')

    if not content and not image_file:
        return JsonResponse({'error': 'Please type a message or attach an image.'}, status=400)

    # -------------------------------------------------------------
    # CASE 1: AI Ownership Verification Phase
    # -------------------------------------------------------------
    if convo.status == Conversation.STATUS_AI_VERIFY:
        if not is_claimant:
            return JsonResponse({'error': 'AI verification is currently in progress with the claimant.'}, status=403)

        # 1. Record Claimant's Response
        user_msg = Message.objects.create(
            conversation=convo,
            sender=request.user,
            content=content,
            image=image_file,
            message_type='IMAGE' if (image_file and not content) else 'TEXT',
        )

        claimant_answers_count = convo.messages.filter(sender=request.user).count()

        if claimant_answers_count < TOTAL_VERIFICATION_STEPS:
            # Generate next question (Step 2 to 6)
            next_step = claimant_answers_count + 1
            history = [
                {'role': 'user' if m.sender else 'assistant', 'content': m.content}
                for m in convo.messages.order_by('created_at')
            ]
            next_q = generate_ai_interview_question(convo.match.lost_item, history, next_step)
            ai_msg_text = f"❓ Question {next_step} of {TOTAL_VERIFICATION_STEPS}:\n{next_q}"

            ai_msg = Message.objects.create(
                conversation=convo,
                is_ai=True,
                sender=None,
                content=ai_msg_text,
                message_type='TEXT',
            )

            return JsonResponse({
                'messages': [
                    _serialize_message(user_msg, request.user),
                    _serialize_message(ai_msg, request.user),
                ],
                'convo_status': convo.status,
                'is_closed': convo.is_closed,
            })

        else:
            # Verification questions completed -> Run AI Ownership Verification
            history = [
                {'role': 'user' if m.sender else 'assistant', 'content': m.content}
                for m in convo.messages.order_by('created_at')
            ]

            # Find proof image (from current upload or previous messages in convo)
            proof_img = image_file
            if not proof_img:
                last_img_msg = convo.messages.filter(image__isnull=False).exclude(image="").last()
                if last_img_msg:
                    proof_img = last_img_msg.image

            eval_result = evaluate_interview_transcript(convo.match.lost_item, history, proof_image=proof_img)

            claim, _ = OwnershipClaim.objects.get_or_create(match=convo.match, claimant=request.user)
            claim.status = OwnershipClaim.STATUS_PENDING
            claim.ai_score = eval_result['match_score']
            claim.ai_confidence = eval_result['confidence']
            claim.ai_reasoning = eval_result['reasoning']
            claim.is_ai_verified = eval_result['is_verified']
            claim.answer_text = eval_result['transcript_summary']
            if proof_img and hasattr(proof_img, 'file'):
                claim.proof_image = proof_img
            claim.save()

            convo.ai_score = eval_result['match_score']
            convo.is_ai_verified = eval_result['is_verified']
            convo.status = Conversation.STATUS_PENDING_FINDER
            convo.save(update_fields=['ai_score', 'is_ai_verified', 'status'])

            if eval_result['is_verified']:
                ai_verdict_text = (
                    f"🎉 AI Verification Assessment: PASSED ({claim.ai_score:.0f}% Match Score)\n\n"
                    f"📊 Confidence Level: {claim.ai_confidence}\n"
                    f"💡 AI Analysis: {claim.ai_reasoning}\n\n"
                    f"✅ Ownership Confirmed: Claimant answers matched the confidential parameters with ≥ 70% confidence. "
                    f"The Finder ({convo.participant_b.get_full_name_or_username()}) has been notified to review this interview and confirm the handover."
                )
                ai_msg = Message.objects.create(
                    conversation=convo,
                    is_ai=True,
                    sender=None,
                    content=ai_verdict_text,
                    message_type='VERDICT',
                )

                # Send anti-spam email notification to Finder (WITHOUT Handover OTP)
                send_ai_verified_claim_email(
                    finder=convo.participant_b,
                    claimant=request.user,
                    found_item=convo.match.found_item,
                    match=convo.match,
                    claim=claim,
                    convo_id=convo.id,
                )

                # In-app notifications
                notify_user(
                    user=convo.participant_b,
                    notif_type='CLAIM',
                    title=f'🎉 Genuine Owner Verified by AI for "{convo.match.found_item.title}"!',
                    body=f'{request.user.get_full_name_or_username()} scored {claim.ai_score:.0f}% in AI verification. Please review the chat and confirm handover.',
                    link=f'/chat/{convo.id}/',
                )
                notify_user(
                    user=request.user,
                    notif_type='CLAIM',
                    title=f'🎉 AI Verified Your Ownership ({claim.ai_score:.0f}%)!',
                    body='You passed AI verification! The finder has been invited to review this interview and confirm the handover.',
                    link=f'/chat/{convo.id}/',
                )

            else:
                ai_verdict_text = (
                    f"⚠️ AI Verification Assessment: Manual Review Required ({claim.ai_score:.0f}% Match Score)\n\n"
                    f"📊 Confidence Level: {claim.ai_confidence}\n"
                    f"💡 AI Analysis: {claim.ai_reasoning}\n\n"
                    f"Your match score is below the 70% automated threshold. "
                    f"Your full interview answers have been forwarded to the finder for manual review."
                )
                ai_msg = Message.objects.create(
                    conversation=convo,
                    is_ai=True,
                    sender=None,
                    content=ai_verdict_text,
                    message_type='VERDICT',
                )
                notify_user(
                    user=convo.participant_b,
                    notif_type='CLAIM',
                    title=f'New ownership claim on "{convo.match.found_item.title}" (AI Score: {claim.ai_score:.0f}%)',
                    body=f'{request.user.get_full_name_or_username()} submitted verification answers ({claim.ai_score:.0f}% score). Please review in chat.',
                    link=f'/chat/{convo.id}/',
                )

            return JsonResponse({
                'messages': [
                    _serialize_message(user_msg, request.user),
                    _serialize_message(ai_msg, request.user),
                ],
                'convo_status': convo.status,
                'is_closed': convo.is_closed,
            })

    # -------------------------------------------------------------
    # CASE 2: PENDING FINDER / ACTIVE Peer-to-Peer Chat
    # -------------------------------------------------------------
    msg = Message.objects.create(
        conversation=convo,
        sender=request.user,
        content=content,
        image=image_file,
        message_type='IMAGE' if (image_file and not content) else 'TEXT',
    )
    return JsonResponse({
        'messages': [_serialize_message(msg, request.user)],
        'convo_status': convo.status,
        'is_closed': convo.is_closed,
    })


@login_required
def poll_messages(request, pk):
    """Return new messages since a given message id (for AJAX polling)."""
    convo = get_object_or_404(Conversation, pk=pk)
    if request.user not in (convo.participant_a, convo.participant_b):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    since_id = int(request.GET.get('since', 0))
    new_msgs = convo.messages.filter(id__gt=since_id).select_related('sender').order_by('created_at')

    # Mark as read for this user
    new_msgs.exclude(sender=request.user).exclude(is_ai=True).update(is_read=True)

    data = [_serialize_message(m, request.user) for m in new_msgs]
    return JsonResponse({
        'messages': data,
        'convo_status': convo.status,
        'is_closed': convo.is_closed,
        'ai_score': convo.ai_score,
        'is_ai_verified': convo.is_ai_verified,
    })


@login_required
@require_POST
def finder_confirm_owner(request, pk):
    """
    Finder reviews AI transcript and clicks 'Confirm & Accept Owner'.
    Releases the 6-digit Handover OTP and activates the direct chat.
    """
    convo = get_object_or_404(Conversation, pk=pk)
    if request.user != convo.participant_b:
        messages.error(request, 'Only the finder can confirm and accept the owner.')
        return redirect('chat:conversation_detail', pk=pk)

    claim = convo.match.claims.filter(claimant=convo.participant_a).first()
    if not claim:
        claim = OwnershipClaim.objects.create(match=convo.match, claimant=convo.participant_a)

    # 1. Update Claim with Finder Confirmation & Generate Handover OTP
    claim.finder_verified = True
    claim.finder_verified_at = timezone.now()
    claim.status = OwnershipClaim.STATUS_ACCEPTED
    otp = claim.generate_handover_otp()
    claim.save()

    # 2. Update Match & Items to VERIFIED / ACCEPTED
    match = convo.match
    match.status = Match.STATUS_ACCEPTED
    match.lost_item.status = 'VERIFIED'
    match.found_item.status = 'VERIFIED'
    match.save(update_fields=['status'])
    match.lost_item.save(update_fields=['status'])
    match.found_item.save(update_fields=['status'])

    # Close/reject other pending matches for these items now that they are paired
    Match.objects.filter(lost_item=match.lost_item).exclude(id=match.id).filter(
        status__in=[Match.STATUS_DETECTED, Match.STATUS_NOTIFIED]
    ).update(status=Match.STATUS_REJECTED)
    Match.objects.filter(found_item=match.found_item).exclude(id=match.id).filter(
        status__in=[Match.STATUS_DETECTED, Match.STATUS_NOTIFIED]
    ).update(status=Match.STATUS_REJECTED)

    # 3. Create ReturnConfirmation record
    ReturnConfirmation.objects.get_or_create(claim=claim)

    # 4. Activate the Conversation
    convo.status = Conversation.STATUS_ACTIVE
    convo.save(update_fields=['status'])

    # 5. Post System Announcement in Chat
    finder_name = request.user.get_full_name_or_username()
    owner_name = convo.participant_a.get_full_name_or_username()
    Message.objects.create(
        conversation=convo,
        is_ai=True,
        sender=None,
        message_type='SYSTEM',
        content=(
            f"🤝 Handover Approved! {finder_name} (Finder) has verified and confirmed {owner_name} as the genuine owner.\n\n"
            f"🔐 The safe 6-digit Handover OTP has been released to the owner. "
            f"You can now coordinate a safe public meeting place right here!"
        ),
    )

    # 6. Notify Claimant with Handover OTP
    notify_user(
        user=convo.participant_a,
        notif_type='CLAIM',
        title='🎉 Finder Confirmed Your Ownership!',
        body=f'{finder_name} has accepted your claim! Your Handover OTP is {otp}. Coordinate in chat now.',
        link=f'/chat/{convo.id}/',
    )

    messages.success(request, f'🎉 You confirmed {owner_name} as the owner! The Handover OTP has been issued.')
    return redirect('chat:conversation_detail', pk=pk)


@login_required
@require_POST
def finder_decline_claim(request, pk):
    """Finder declines the claim after reviewing transcript."""
    convo = get_object_or_404(Conversation, pk=pk)
    if request.user != convo.participant_b:
        messages.error(request, 'Only the finder can decline the claim.')
        return redirect('chat:conversation_detail', pk=pk)

    claim = convo.match.claims.filter(claimant=convo.participant_a).first()
    reason = request.POST.get('reason', 'Verification answers did not match sufficiently.').strip()
    if claim:
        claim.status = OwnershipClaim.STATUS_REJECTED
        claim.rejection_reason = reason
        claim.save(update_fields=['status', 'rejection_reason'])

    convo.status = Conversation.STATUS_CLOSED
    convo.save(update_fields=['status'])

    Message.objects.create(
        conversation=convo,
        is_ai=True,
        sender=None,
        message_type='SYSTEM',
        content=f"❌ Claim was declined by the finder. Reason: {reason}",
    )

    notify_user(
        user=convo.participant_a,
        notif_type='CLAIM',
        title='Ownership claim declined.',
        body=f'The finder declined the claim. Reason: {reason}',
        link=f'/matching/{convo.match.id}/',
    )

    messages.info(request, 'Ownership claim has been declined.')
    return redirect('matching:match_detail', pk=convo.match.id)
