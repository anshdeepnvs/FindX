from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import EmailOTP

User = get_user_model()


class AccountsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
            is_email_verified=False
        )

    def test_email_otp_generation_and_validity(self):
        otp = EmailOTP.generate_otp(self.user)
        self.assertEqual(len(otp.otp_code), 6)
        self.assertTrue(otp.is_valid())

        # Test expired OTP
        otp.created_at = timezone.now() - timedelta(minutes=15)
        otp.save()
        self.assertFalse(otp.is_valid())

    def test_verify_otp_flow(self):
        otp = EmailOTP.generate_otp(self.user)
        session = self.client.session
        session["verification_user_id"] = self.user.id
        session.save()

        response = self.client.post("/accounts/verify-otp/", {"otp_code": otp.otp_code})
        self.assertRedirects(response, "/dashboard/")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_signup_requires_phone_number(self):
        # Missing phone number should fail
        response = self.client.post("/accounts/register/", {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "strongpassword123",
            "confirm_password": "strongpassword123",
            "phone_number": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "phone_number", "This field is required.")

    def test_signup_with_phone_number_succeeds_and_creates_email_otp(self):
        # Valid signup with phone number
        response = self.client.post("/accounts/register/", {
            "username": "validuser",
            "email": "validuser@example.com",
            "phone_number": "9876543210",
            "password": "strongpassword123",
            "confirm_password": "strongpassword123",
        })
        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username="validuser")
        self.assertEqual(created_user.phone_number, "9876543210")
        self.assertFalse(created_user.is_email_verified)
        # Verify an Email OTP was generated for this user
        self.assertTrue(EmailOTP.objects.filter(user=created_user).exists())

    def test_login_with_username_and_verified_user(self):
        # Set user as verified
        self.user.is_email_verified = True
        self.user.save()

        response = self.client.post("/accounts/login/", {
            "username": "testuser",
            "password": "testpassword123",
        })
        self.assertRedirects(response, "/dashboard/")
        self.assertTrue("_auth_user_id" in self.client.session)

    def test_login_with_email(self):
        self.user.is_email_verified = True
        self.user.save()

        response = self.client.post("/accounts/login/", {
            "username": "test@example.com",
            "password": "testpassword123",
        })
        self.assertRedirects(response, "/dashboard/")
        self.assertTrue("_auth_user_id" in self.client.session)

    def test_login_unverified_redirects_to_verify_otp(self):
        # Unverified user logs in
        self.user.is_email_verified = False
        self.user.save()

        response = self.client.post("/accounts/login/", {
            "username": "testuser",
            "password": "testpassword123",
        })
        self.assertRedirects(response, "/accounts/verify-otp/")

    def test_resend_otp_creates_new_code(self):
        session = self.client.session
        session["verification_user_id"] = self.user.id
        session.save()

        initial_count = EmailOTP.objects.filter(user=self.user).count()
        response = self.client.get("/accounts/resend-otp/")
        self.assertRedirects(response, "/accounts/verify-otp/")

        new_count = EmailOTP.objects.filter(user=self.user).count()
        self.assertEqual(new_count, initial_count + 1)

    def test_upload_and_remove_profile_avatar(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.user.is_email_verified = True
        self.user.save()
        self.client.login(username="testuser", password="testpassword123")

        # Create dummy image file
        image_content = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
        image = SimpleUploadedFile("avatar.gif", image_content, content_type="image/gif")

        response = self.client.post("/accounts/profile/", {"avatar": image})
        self.assertRedirects(response, "/accounts/profile/")
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))

        # Test remove avatar
        response = self.client.post("/accounts/profile/", {"remove_avatar": "1"})
        self.assertRedirects(response, "/accounts/profile/")
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.avatar))


