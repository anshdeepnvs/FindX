from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import OwnershipClaim, ReturnConfirmation
from matching.models import Match
from notifications.utils import notify_user
from .ai_verifier import (
    evaluate_claim_ownership,
    generate_ai_interview_question,
    evaluate_interview_transcript,
    TOTAL_VERIFICATION_STEPS,
)
from .emails import send_ai_verified_claim_email


def _format_local_time():
    """Formats current time in user-friendly local format (e.g. '11:42 AM')."""
    return timezone.localtime().strftime("%I:%M %p").lstrip('0')


@login_required
def submit_claim(request, match_id):
    match = get_object_or_404(Match, pk=match_id)

    # Only the lost-item reporter can submit a claim
    if request.user != match.lost_item.reporter:
        messages.error(request, 'Only the owner of the lost item can submit a claim.')
        return redirect('matching:match_detail', pk=match_id)

    # Get or create claim
    claim, _ = OwnershipClaim.objects.get_or_create(
        match=match,
        claimant=request.user,
        defaults={'status': OwnershipClaim.STATUS_IN_PROGRESS}
    )

    from chat.models import Conversation, Message
    convo, _ = Conversation.objects.get_or_create(
        match=match,
        defaults={
            'participant_a': match.lost_item.reporter,
            'participant_b': match.found_item.reporter,
            'status': Conversation.STATUS_AI_VERIFY,
        }
    )

    # Seed AI greeting & Question 1 if conversation has no messages
    if convo.messages.count() == 0:
        q1 = generate_ai_interview_question(match.lost_item, [], 1)
        first_msg = (
            f"👋 Hello {request.user.get_full_name_or_username()}! I am FindX's AI Verification Officer.\n\n"
            f"To verify your ownership of \"{match.found_item.title}\" and ensure community safety, "
            f"I will ask you adaptive verification questions (typically 2 to 6 questions depending on your details) based on item parameters.\n\n"
            f"❓ Question 1 (of up to {TOTAL_VERIFICATION_STEPS}):\n{q1}"
        )
        Message.objects.create(
            conversation=convo,
            is_ai=True,
            sender=None,
            content=first_msg,
            message_type='TEXT',
        )

    # Fallback support for direct POST submission
    if request.method == 'POST' and 'answer_text' in request.POST:
        answer = request.POST.get('answer_text', '').strip()
        add_info = request.POST.get('additional_info', '').strip()
        proof_file = request.FILES.get('proof_image')

        user_content = f"{answer} {add_info}".strip()
        user_msg = Message.objects.create(
            conversation=convo,
            sender=request.user,
            content=user_content,
            image=proof_file,
            message_type='IMAGE' if (proof_file and not user_content) else 'TEXT',
        )

        history = [
            {'role': 'user' if m.sender else 'assistant', 'content': m.content}
            for m in convo.messages.order_by('created_at')
        ]
        eval_result = evaluate_interview_transcript(match.lost_item, history, proof_image=proof_file)

        claim.answer_text = user_content
        claim.ai_score = eval_result["match_score"]
        claim.ai_confidence = eval_result["confidence"]
        claim.ai_reasoning = eval_result["reasoning"]
        claim.is_ai_verified = eval_result["is_verified"]
        if proof_file:
            claim.proof_image = proof_file
        claim.status = OwnershipClaim.STATUS_PENDING
        claim.save()

        convo.ai_score = eval_result["match_score"]
        convo.is_ai_verified = eval_result["is_verified"]
        convo.status = Conversation.STATUS_PENDING_FINDER
        convo.save(update_fields=['ai_score', 'is_ai_verified', 'status'])

        if eval_result["is_verified"]:
            Message.objects.create(
                conversation=convo,
                is_ai=True,
                sender=None,
                content=f"🎉 AI Verification PASSED ({claim.ai_score:.0f}% Match Score)\n\nConfidence: {claim.ai_confidence}\nAnalysis: {claim.ai_reasoning}\n\nClaimant ownership verified by AI with ≥ 70% match. The Finder has been notified to review and confirm handover.",
                message_type='VERDICT',
            )
            send_ai_verified_claim_email(
                finder=match.found_item.reporter,
                claimant=request.user,
                found_item=match.found_item,
                match=match,
                claim=claim,
                convo_id=convo.id,
            )
            notify_user(
                user=match.found_item.reporter,
                notif_type='CLAIM',
                title=f'🎉 Genuine Owner Verified by AI for "{match.found_item.title}"!',
                body=f'{request.user.get_full_name_or_username()} scored {claim.ai_score:.0f}% in AI verification. Please review in chat.',
                link=f'/chat/{convo.id}/',
            )

        return redirect('chat:conversation_detail', pk=convo.id)

    # Redirect claimant straight to unified chat
    return redirect('chat:conversation_detail', pk=convo.id)


@login_required
@require_POST
def ai_chat_send(request, match_id):
    """
    AJAX handler for claimant responses in the AI Verification Chat.
    Guides user through multi-turn questions and triggers evaluation.
    """
    match = get_object_or_404(Match, pk=match_id)
    if request.user != match.lost_item.reporter:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    claim = match.claims.filter(claimant=request.user).first()
    if not claim:
        return JsonResponse({'error': 'Verification session not found'}, status=400)

    from chat.models import Conversation, Message
    convo, _ = Conversation.objects.get_or_create(
        match=match,
        defaults={
            'participant_a': match.lost_item.reporter,
            'participant_b': match.found_item.reporter,
            'status': Conversation.STATUS_AI_VERIFY,
        }
    )

    user_text = request.POST.get('message', '').strip()
    image_file = request.FILES.get('image') or request.FILES.get('proof_image')

    if not user_text and not image_file:
        return JsonResponse({'error': 'Please provide an answer or image.'}, status=400)

    # Record message in Conversation
    user_msg = Message.objects.create(
        conversation=convo,
        sender=request.user,
        content=user_text,
        image=image_file,
        message_type='IMAGE' if (image_file and not user_text) else 'TEXT',
    )

    user_answers_count = convo.messages.filter(sender=request.user).count()

    history = [
        {'role': 'user' if m.sender else 'assistant', 'content': m.content}
        for m in convo.messages.order_by('created_at')
    ]
    proof_img = image_file
    if not proof_img:
        last_img_msg = convo.messages.filter(image__isnull=False).exclude(image="").last()
        if last_img_msg:
            proof_img = last_img_msg.image

    eval_result = None
    should_conclude = False

    # Adaptive Check: Early exit if user has provided at least 2 conclusive answers
    if user_answers_count >= 2:
        eval_result = evaluate_interview_transcript(match.lost_item, history, proof_image=proof_img)
        if eval_result.get('is_verified') and eval_result.get('match_score', 0) >= 75.0:
            should_conclude = True

    # Exit if maximum steps reached
    if user_answers_count >= TOTAL_VERIFICATION_STEPS:
        should_conclude = True
        if eval_result is None:
            eval_result = evaluate_interview_transcript(match.lost_item, history, proof_image=proof_img)

    if not should_conclude:
        next_step = user_answers_count + 1
        next_q = generate_ai_interview_question(match.lost_item, history, next_step)
        ai_response_text = f"❓ Follow-up Question {next_step} (Step {next_step} of up to {TOTAL_VERIFICATION_STEPS}):\n{next_q}"

        ai_msg = Message.objects.create(
            conversation=convo,
            is_ai=True,
            sender=None,
            content=ai_response_text,
            message_type='TEXT',
        )

        return JsonResponse({
            'status': 'in_progress',
            'step': next_step,
            'ai_message': ai_response_text,
            'timestamp': _format_local_time(),
        })

    else:
        # Verification questions answered / verified early -> Deliver verdict
        claim.ai_score = eval_result['match_score']
        claim.ai_confidence = eval_result['confidence']
        claim.ai_reasoning = eval_result['reasoning']
        claim.is_ai_verified = eval_result['is_verified']
        claim.answer_text = eval_result['transcript_summary']
        if proof_img and hasattr(proof_img, 'file'):
            claim.proof_image = proof_img
        claim.status = OwnershipClaim.STATUS_PENDING
        claim.save()

        convo.ai_score = eval_result['match_score']
        convo.is_ai_verified = eval_result['is_verified']
        convo.status = Conversation.STATUS_PENDING_FINDER
        convo.save(update_fields=['ai_score', 'is_ai_verified', 'status'])

        if eval_result['is_verified']:
            early_note = f" (Verified early in {user_answers_count} questions)" if user_answers_count < TOTAL_VERIFICATION_STEPS else ""
            ai_verdict_msg = (
                f"🎉 Verification Completed Successfully!{early_note}\n\n"
                f"📊 AI Ownership Match Score: {claim.ai_score:.0f}%\n"
                f"🔒 Confidence Level: {claim.ai_confidence}\n\n"
                f"💡 AI Analysis: {claim.ai_reasoning}\n\n"
                f"✅ Ownership Confirmed: Your score meets the 70% threshold. "
                f"The finder has been notified and invited to review this chat transcript and confirm the handover."
            )
            Message.objects.create(
                conversation=convo,
                is_ai=True,
                sender=None,
                content=ai_verdict_msg,
                message_type='VERDICT',
            )

            send_ai_verified_claim_email(
                finder=match.found_item.reporter,
                claimant=request.user,
                found_item=match.found_item,
                match=match,
                claim=claim,
                convo_id=convo.id,
            )

            notify_user(
                user=match.found_item.reporter,
                notif_type='CLAIM',
                title=f'🎉 Genuine Owner Verified by AI for "{match.found_item.title}"!',
                body=f'{request.user.get_full_name_or_username()} scored {claim.ai_score:.0f}% in AI verification. Please review in chat.',
                link=f'/chat/{convo.id}/',
            )

            return JsonResponse({
                'status': 'accepted',
                'score': claim.ai_score,
                'confidence': claim.ai_confidence,
                'reasoning': claim.ai_reasoning,
                'is_verified': True,
                'ai_message': ai_verdict_msg,
                'chat_url': f'/chat/{convo.id}/',
            })

        else:
            ai_verdict_msg = (
                f"Verification Assessment Completed.\n\n"
                f"📊 AI Ownership Match Score: {claim.ai_score:.0f}%\n"
                f"🔒 Confidence Level: {claim.ai_confidence}\n\n"
                f"💡 AI Analysis: {claim.ai_reasoning}\n\n"
                f"⚠️ Manual Review Required: Your score is below the 70% automated threshold. "
                f"Your full interview transcript has been forwarded to the finder for manual review."
            )
            Message.objects.create(
                conversation=convo,
                is_ai=True,
                sender=None,
                content=ai_verdict_msg,
                message_type='VERDICT',
            )

            return JsonResponse({
                'status': 'pending',
                'score': claim.ai_score,
                'confidence': claim.ai_confidence,
                'reasoning': claim.ai_reasoning,
                'is_verified': False,
                'ai_message': ai_verdict_msg,
                'chat_url': f'/chat/{convo.id}/',
            })


@login_required
def review_claim(request, claim_id):
    claim = get_object_or_404(
        OwnershipClaim.objects.select_related('match', 'claimant', 'match__lost_item', 'match__found_item'),
        pk=claim_id
    )

    # Only the finder can review
    if request.user != claim.match.found_item.reporter:
        messages.error(request, 'Only the finder can review this claim.')
        return redirect('core:dashboard')

    private = getattr(claim.match.lost_item, 'private_detail', None)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            claim.status = OwnershipClaim.STATUS_ACCEPTED
            claim.finder_verified = True
            claim.finder_verified_at = timezone.now()
            claim.generate_handover_otp()
            claim.save()
            claim.match.status = Match.STATUS_ACCEPTED
            claim.match.lost_item.status = 'VERIFIED'
            claim.match.found_item.status = 'VERIFIED'
            claim.match.save(update_fields=['status'])
            claim.match.lost_item.save(update_fields=['status'])
            claim.match.found_item.save(update_fields=['status'])

            # Close/reject other pending matches for these items
            Match.objects.filter(lost_item=claim.match.lost_item).exclude(id=claim.match.id).filter(
                status__in=[Match.STATUS_DETECTED, Match.STATUS_NOTIFIED]
            ).update(status=Match.STATUS_REJECTED)
            Match.objects.filter(found_item=claim.match.found_item).exclude(id=claim.match.id).filter(
                status__in=[Match.STATUS_DETECTED, Match.STATUS_NOTIFIED]
            ).update(status=Match.STATUS_REJECTED)

            # Create return confirmation record
            ReturnConfirmation.objects.get_or_create(claim=claim)

            # Open conversation
            from chat.models import Conversation
            Conversation.objects.get_or_create(
                match=claim.match,
                defaults={
                    'participant_a': claim.match.lost_item.reporter,
                    'participant_b': claim.match.found_item.reporter,
                }
            )

            notify_user(
                user=claim.claimant,
                notif_type='CLAIM',
                title='🎉 Your ownership claim was accepted!',
                body='The finder has accepted your claim. You can now chat and arrange the return.',
                link=f'/claims/{claim.id}/return/',
            )
            messages.success(request, 'Claim accepted! A chat has been opened between both parties.')

        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            claim.status = OwnershipClaim.STATUS_REJECTED
            claim.rejection_reason = reason
            claim.save(update_fields=['status', 'rejection_reason'])
            notify_user(
                user=claim.claimant,
                notif_type='CLAIM',
                title='Your ownership claim was rejected.',
                body=f'Reason: {reason}' if reason else 'The finder did not accept your claim.',
                link=f'/matching/{claim.match.id}/',
            )
            messages.info(request, 'Claim rejected.')

        return redirect('claims:review_claim', claim_id=claim_id)

    ctx = {'claim': claim, 'private': private}
    return render(request, 'claims/review_claim.html', ctx)


@login_required
def return_confirm(request, claim_id):
    """Finder marks item as physically returned."""
    claim = get_object_or_404(OwnershipClaim, pk=claim_id, status=OwnershipClaim.STATUS_ACCEPTED)
    if request.user != claim.match.found_item.reporter:
        messages.error(request, 'Only the finder can mark the item as returned.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        rc, _ = ReturnConfirmation.objects.get_or_create(claim=claim)
        rc.finder_confirmed    = True
        rc.finder_confirmed_at = timezone.now()
        rc.save()

        notify_user(
            user=claim.claimant,
            notif_type='RETURN',
            title='The finder has marked the item as returned!',
            body='Please confirm you have received your item.',
            link=f'/claims/{claim.id}/receipt/',
        )
        messages.success(request, 'Great! We have notified the owner to confirm receipt.')
        return redirect('core:dashboard')

    return render(request, 'claims/return_confirm.html', {'claim': claim})


@login_required
def receipt_confirm(request, claim_id):
    """Owner confirms they received the item."""
    claim = get_object_or_404(OwnershipClaim, pk=claim_id, status=OwnershipClaim.STATUS_ACCEPTED)
    if request.user != claim.claimant:
        messages.error(request, 'Only the item owner can confirm receipt.')
        return redirect('core:dashboard')

    rc = get_object_or_404(ReturnConfirmation, claim=claim)

    if request.method == 'POST':
        confirmed = request.POST.get('confirmed') == 'yes'
        if confirmed:
            rc.owner_confirmed    = True
            rc.owner_confirmed_at = timezone.now()
            rc.save()

            # Mark everything returned
            claim.match.status = Match.STATUS_RETURNED
            claim.match.lost_item.status  = 'RETURNED'
            claim.match.lost_item.is_active = False
            claim.match.found_item.status = 'RETURNED'
            claim.match.found_item.is_active = False
            claim.match.save(update_fields=['status'])
            claim.match.lost_item.save(update_fields=['status', 'is_active'])
            claim.match.found_item.save(update_fields=['status', 'is_active'])

            # Close the secure chat conversation
            try:
                if hasattr(claim.match, 'conversation'):
                    convo = claim.match.conversation
                    convo.is_active = False
                    convo.save(update_fields=['is_active'])
            except Exception:
                pass

            notify_user(
                user=claim.match.found_item.reporter,
                notif_type='RETURN',
                title='🎉 Item successfully returned!',
                body='The owner has confirmed they received the item. Thank you for helping reunite them!',
                link='/',
            )
            messages.success(request, '🎉 Wonderful! Your item has been successfully returned.')
            return redirect('claims:success', claim_id=claim.id)
        else:
            messages.warning(request, 'Please contact the finder via chat if you have not received the item yet.')
            return redirect('core:dashboard')

    ctx = {'claim': claim, 'rc': rc}
    return render(request, 'claims/receipt_confirm.html', ctx)


@login_required
def return_success(request, claim_id):
    claim = get_object_or_404(OwnershipClaim, pk=claim_id)
    return render(request, 'claims/success.html', {'claim': claim})
