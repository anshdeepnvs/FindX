from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegistrationForm(forms.ModelForm):
    phone_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 9876543210"}),
        help_text="Required for identity verification and anti-scam records."
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Create a secure password"})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirm your password"})
    )

    class Meta:
        model = User
        fields = ["username", "email", "phone_number"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Choose a username"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        # Strip spaces and hyphens
        clean_digits = "".join(filter(str.isdigit, phone))
        if len(clean_digits) < 10:
            raise forms.ValidationError("Please enter a valid phone number (at least 10 digits).")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get("password")
        pwd_confirm = cleaned_data.get("confirm_password")
        if pwd and pwd_confirm and pwd != pwd_confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "6-digit OTP",
            "style": "letter-spacing: 6px; font-size: 1.5rem; text-align: center; font-weight: 700;",
            "autofocus": "autofocus",
            "maxlength": "6",
        }),
        help_text="Enter the 6-digit code sent to your registered email."
    )
