import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

def send_attendance_email(student_name, time_str, email_address):
    """
    Sends an automated email when attendance is marked using standard smtplib.
    Requires SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS in environment.
    Falls back to mock logging if credentials aren't set.
    """
    if not email_address:
        logging.warning(f"No email address provided for student {student_name}, skipping.")
        return False
        
    subject = "Daily Attendance Update"
    body = f"Your child {student_name} is present today at {time_str}"
    
    smtp_server = os.environ.get("SMTP_SERVER", "")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    
    if not smtp_server or not smtp_user:
        logging.info(f"[MOCK EMAIL Triggered] To: {email_address} | Subject: {subject} | Body: {body}")
        print(f"\n>>>> EMAIL MOCKED \nTo: {email_address}\nSubject: {subject}\nBody: {body}\n")
        return True
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        text = msg.as_string()
        server.sendmail(smtp_user, email_address, text)
        server.quit()
        
        logging.info(f"Successfully delivered Email to {email_address}")
        return True
    except Exception as e:
        logging.error(f"Error sending email to {email_address}: {str(e)}")
        return False
