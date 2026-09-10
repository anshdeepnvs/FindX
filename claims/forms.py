from django import forms
from .models import OwnershipClaim


class SubmitClaimForm(forms.ModelForm):
    class Meta:
        model = OwnershipClaim
        fields = ["answer_text", "proof_image", "additional_info"]
        widgets = {
            "answer_text": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Answer the finder's challenge question and describe all private details you know:\n- Specific scratches, stickers, or cosmetic marks\n- Lockscreen wallpaper / PIN hint\n- Names on cards, bills, or items located inside\n- Serial number, model code, or purchase invoice numbers"
            }),
            "proof_image": forms.FileInput(attrs={
                "class": "form-control",
                "accept": "image/*"
            }),
            "additional_info": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Explain the approximate time/place you lost it or contact preference."
            }),
        }


class VerifyHandoverOTPForm(forms.Form):
    handover_otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter claimant's 6-digit OTP",
            "style": "letter-spacing: 4px; font-size: 1.2rem; text-align: center; font-weight: 700;",
            "maxlength": "6",
        }),
        help_text="Ask the claimant for their secret Handover PIN to officially release the item."
    )
