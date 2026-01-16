"""
Email service for sending notifications and verification emails.
"""

import asyncio
from email.message import EmailMessage
from typing import Optional

from jinja2 import Template

from app.core.config import settings


class EmailService:
    """
    Email service for sending transactional emails.

    Uses SMTP for email delivery with Jinja2 for templating.
    """

    def __init__(self):
        """Initialize email service."""
        self.enabled = settings.smtp.enabled
        self.lock = asyncio.Lock()

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body (optional)

        Returns:
            True if email sent successfully
        """
        if not self.enabled:
            # Log email in development mode
            if settings.app.app_debug:
                print(f"\n{'='*60}")
                print(f"EMAIL TO: {to}")
                print(f"SUBJECT: {subject}")
                print(f"{'='*60}")
                print(f"HTML:\n{html_body}")
                print(f"{'='*60}\n")
            return True

        if not settings.smtp.host:
            return False

        try:
            # Create message
            message = EmailMessage()
            message["From"] = f"{settings.smtp.from_name} <{settings.smtp.from_email}>"
            message["To"] = to
            message["Subject"] = subject

            message.set_content(text_body or html_body)
            message.add_alternative(html_body, subtype="html")

            # Send email
            # Port 465 uses SSL (direct SSL), Port 587 uses TLS (start_tls)
            async with self.lock:
                if settings.smtp.port == 465:
                    # Use SSL for port 465 - run in thread pool since smtplib is sync
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._send_ssl_sync,
                        message,
                    )
                else:
                    # Use aiosmtplib with TLS for port 587
                    import aiosmtplib
                    await aiosmtplib.send(
                        message,
                        hostname=settings.smtp.host,
                        port=settings.smtp.port,
                        username=settings.smtp.username if settings.smtp.username else None,
                        password=settings.smtp.password if settings.smtp.password else None,
                        use_tls=settings.smtp.use_tls,
                    )

            return True

        except Exception as e:
            print(f"Failed to send email: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _send_ssl_sync(self, message: EmailMessage) -> None:
        """Send email using SMTP SSL (port 465) - synchronous."""
        import smtplib
        from ssl import create_default_context

        # Create SSL context
        context = create_default_context()

        with smtplib.SMTP_SSL(
            settings.smtp.host,
            settings.smtp.port,
            context=context,
            timeout=30,
        ) as smtp:
            if settings.smtp.username:
                smtp.login(settings.smtp.username, settings.smtp.password)
            smtp.send_message(message)

    async def send_verification_code(
        self,
        to: str,
        code: str,
        expiry_minutes: int = 10,
    ) -> bool:
        """
        Send verification code email.

        Args:
            to: Recipient email
            code: Verification code
            expiry_minutes: Code expiry in minutes

        Returns:
            True if sent successfully
        """
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .code {{ font-size: 32px; font-weight: bold; letter-spacing: 5px;
                        text-align: center; padding: 20px; background: #f5f5f5;
                        border-radius: 8px; margin: 20px 0; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>验证码</h2>
                <p>您正在注册 Noveris AI 账户，您的验证码是：</p>
                <div class="code">{code}</div>
                <p>此验证码将在 {expiry_minutes} 分钟后过期。</p>
                <p>如果您没有请求此验证码，请忽略此邮件。</p>
                <div class="footer">
                    <p>&copy; 2025 Noveris AI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""您的验证码是: {code}

此验证码将在 {expiry_minutes} 分钟后过期。

如果您没有请求此验证码，请忽略此邮件。"""

        return await self.send_email(
            to=to,
            subject="验证码 - Noveris AI",
            html_body=html_body,
            text_body=text_body,
        )

    async def send_password_reset(
        self,
        to: str,
        reset_link: str,
        expiry_minutes: int = 60,
    ) -> bool:
        """
        Send password reset email.

        Args:
            to: Recipient email
            reset_link: Password reset link
            expiry_minutes: Link expiry in minutes

        Returns:
            True if sent successfully
        """
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #007bff;
                           color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>重置密码</h2>
                <p>我们收到了您的密码重置请求。点击下面的按钮重置密码：</p>
                <div style="text-align: center;">
                    <a href="{reset_link}" class="button">重置密码</a>
                </div>
                <p>或者复制以下链接到浏览器：</p>
                <p style="word-break: break-all; color: #007bff;">{reset_link}</p>
                <p>此链接将在 {expiry_minutes} 分钟后过期。</p>
                <p>如果您没有请求重置密码，请忽略此邮件。</p>
                <div class="footer">
                    <p>&copy; 2025 Noveris AI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""我们收到了您的密码重置请求。

点击下面的链接重置密码:
{reset_link}

此链接将在 {expiry_minutes} 分钟后过期。

如果您没有请求重置密码，请忽略此邮件。"""

        return await self.send_email(
            to=to,
            subject="重置密码 - Noveris AI",
            html_body=html_body,
            text_body=text_body,
        )

    async def send_password_reset_code(
        self,
        to: str,
        code: str,
        expiry_minutes: int = 60,
    ) -> bool:
        """
        Send password reset code email.

        Args:
            to: Recipient email
            code: Reset code
            expiry_minutes: Code expiry in minutes

        Returns:
            True if sent successfully
        """
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .code {{ font-size: 32px; font-weight: bold; letter-spacing: 5px;
                        text-align: center; padding: 20px; background: #f5f5f5;
                        border-radius: 8px; margin: 20px 0; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>重置密码</h2>
                <p>我们收到了您的密码重置请求。您的重置验证码是：</p>
                <div class="code">{code}</div>
                <p>此验证码将在 {expiry_minutes} 分钟后过期。</p>
                <p>如果您没有请求重置密码，请忽略此邮件。</p>
                <div class="footer">
                    <p>&copy; 2025 Noveris AI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""我们收到了您的密码重置请求。

您的重置验证码是: {code}

此验证码将在 {expiry_minutes} 分钟后过期。

如果您没有请求重置密码，请忽略此邮件。"""

        return await self.send_email(
            to=to,
            subject="重置密码验证码 - Noveris AI",
            html_body=html_body,
            text_body=text_body,
        )

    async def send_welcome(
        self,
        to: str,
        name: str,
    ) -> bool:
        """
        Send welcome email to new users.

        Args:
            to: Recipient email
            name: User's name

        Returns:
            True if sent successfully
        """
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>欢迎加入 Noveris AI!</h2>
                <p>你好 {name}，</p>
                <p>感谢您注册 Noveris AI。您的账户已成功创建。</p>
                <p>现在您可以开始使用我们的服务了。</p>
                <div class="footer">
                    <p>&copy; 2025 Noveris AI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""你好 {name}，

感谢您注册 Noveris AI。您的账户已成功创建。

现在您可以开始使用我们的服务了。"""

        return await self.send_email(
            to=to,
            subject="欢迎加入 Noveris AI!",
            html_body=html_body,
            text_body=text_body,
        )
