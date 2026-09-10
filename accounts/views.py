from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .forms import UserRegistrationForm, OTPVerificationForm
from .models import EmailOTP
from .emails import send_otp_email

User = get_user_model()


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.is_email_verified = False
            user.save()

            # Generate OTP
            otp_obj = EmailOTP.generate_otp(user)

            # Send Email (via SMTP or dev console)
            success, err_msg = send_otp_email(user, otp_obj.otp_code)

            # Store user_id in session for verification
            request.session["verification_user_id"] = user.id

            is_smtp = getattr(settings, "IS_SMTP_CONFIGURED", False)
            if success:
                if is_smtp:
                    messages.success(
                        request,
                        f"Account created successfully! A 6-digit OTP has been sent to {user.email}. Please check your inbox (and spam folder)."
                    )
                else:
                    messages.warning(
                        request,
                        f"Account created! Note: Real email was NOT sent because your Gmail credentials in .env are still placeholders. To send live emails to inboxes, add your Gmail and App Password to .env. (Testing OTP: {otp_obj.otp_code})"
                    )
            else:
                messages.error(
                    request,
                    f"Account created, but Gmail SMTP failed ({err_msg}). Please check your credentials in .env. (Testing OTP: {otp_obj.otp_code})"
                )

            return redirect("accounts:verify_otp")
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def verify_otp_view(request):
    user_id = request.session.get("verification_user_id")
    if user_id:
        user = get_object_or_404(User, id=user_id)
    elif request.user.is_authenticated and not request.user.is_email_verified:
        user = request.user
    else:
        if request.user.is_authenticated and request.user.is_email_verified:
            messages.info(request, "Your email is already verified.")
            return redirect("core:home")
        messages.warning(request, "No pending verification found. Please log in or register.")
        return redirect("accounts:login")

    # Check if user has an active valid OTP, if not generate and send one
    active_otp = EmailOTP.objects.filter(user=user, is_used=False).order_by("-created_at").first()
    if not active_otp or not active_otp.is_valid():
        active_otp = EmailOTP.generate_otp(user)
        send_otp_email(user, active_otp.otp_code)

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["otp_code"].strip()
            # Match against latest valid unused OTP for this user
            otp_obj = EmailOTP.objects.filter(user=user, otp_code=code, is_used=False).order_by("-created_at").first()

            if otp_obj and otp_obj.is_valid():
                otp_obj.is_used = True
                otp_obj.save()

                user.is_email_verified = True
                user.save()

                login(request, user)
                if "verification_user_id" in request.session:
                    del request.session["verification_user_id"]

                messages.success(request, "🎉 Email verified successfully! Your account is now fully protected and verified.")
                return redirect("core:dashboard")
            else:
                messages.error(request, "Invalid or expired OTP code. Please check the code or request a new one.")
    else:
        form = OTPVerificationForm()

    is_smtp = getattr(settings, "IS_SMTP_CONFIGURED", False)
    context = {
        "form": form,
        "email": user.email,
        "is_smtp": is_smtp,
        "dev_otp": active_otp.otp_code if not is_smtp else None,
    }
    return render(request, "accounts/verify_otp.html", context)


def resend_otp_view(request):
    user_id = request.session.get("verification_user_id")
    if user_id:
        user = get_object_or_404(User, id=user_id)
    elif request.user.is_authenticated and not request.user.is_email_verified:
        user = request.user
    else:
        messages.warning(request, "Session expired. Please log in.")
        return redirect("accounts:login")

    otp_obj = EmailOTP.generate_otp(user)
    success, err_msg = send_otp_email(user, otp_obj.otp_code)

    is_smtp = getattr(settings, "IS_SMTP_CONFIGURED", False)
    if success:
        if is_smtp:
            messages.success(request, f"A fresh OTP has been sent to your email ({user.email}).")
        else:
            messages.warning(
                request,
                f"New OTP generated! Real email not sent because .env has placeholder credentials. (Dev OTP: {otp_obj.otp_code})"
            )
    else:
        messages.error(
            request,
            f"Gmail SMTP error ({err_msg}). Please check .env. (Dev OTP: {otp_obj.otp_code})"
        )

    return redirect("accounts:verify_otp")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    next_url = request.GET.get("next") or request.POST.get("next") or "core:dashboard"

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Try authenticating directly with username
        user = authenticate(request, username=identifier, password=password)

        # If that fails, try looking up by email address
        if user is None and "@" in identifier:
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                user = None

        if user is not None:
            login(request, user)

            # If user has not verified their email yet, guide them to verify
            if not user.is_email_verified:
                request.session["verification_user_id"] = user.id
                messages.warning(
                    request,
                    f"Welcome back, {user.username}! Please verify your email to access all anti-scam features."
                )
                return redirect("accounts:verify_otp")

            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username/email or password. Please try again.")
            form = AuthenticationForm(request, data=request.POST)
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been safely logged out.")
    return redirect("core:home")


@login_required
def profile_view(request):
    user = request.user

    if request.method == "POST":
        if "avatar" in request.FILES:
            user.avatar = request.FILES["avatar"]
            user.save(update_fields=["avatar"])
            messages.success(request, "Profile photo updated successfully!")
        elif "remove_avatar" in request.POST:
            if user.avatar:
                user.avatar.delete(save=False)
            user.avatar = None
            user.save(update_fields=["avatar"])
            messages.info(request, "Profile photo removed.")
        elif "bio" in request.POST or "first_name" in request.POST:
            user.first_name = request.POST.get("first_name", user.first_name).strip()
            user.last_name = request.POST.get("last_name", user.last_name).strip()
            user.bio = request.POST.get("bio", user.bio).strip()
            phone = request.POST.get("phone_number", user.phone_number).strip()
            if phone:
                user.phone_number = phone
            user.save()
            messages.success(request, "Profile updated successfully!")
        return redirect("accounts:profile")

    my_items = user.reported_items.all().select_related("category").order_by("-created_at")
    my_claims = user.ownership_claims.all().select_related("match__found_item").order_by("-created_at")

    # Claims received on items reported as FOUND by this user
    from claims.models import OwnershipClaim
    received_claims = OwnershipClaim.objects.filter(
        match__found_item__reporter=user
    ).select_related("claimant", "match__lost_item").order_by("-created_at")

    context = {
        "user": user,
        "my_items": my_items,
        "my_claims": my_claims,
        "received_claims": received_claims,
    }
    return render(request, "accounts/profile.html", context)
