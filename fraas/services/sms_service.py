import os
import requests
import logging

def send_attendance_sms(student_name, class_name, time_str, date_str, phone_number):
    """
    Sends an automated SMS using Fast2SMS when attendance is newly marked.
    If no API key is set, it mocks the send action and logs it.
    Does not block the main thread execution due to timeout/fail safes.
    """
    if not phone_number:
        logging.warning(f"No phone number provided for student {student_name}, skipping SMS.")
        return False
        
    message = f"Dear Parent, {student_name} (Class: {class_name}) is present at {time_str} on {date_str}"
    api_key = os.environ.get("FAST2SMS_API_KEY", "")
    
    if not api_key:
        logging.info(f"[MOCK SMS Triggered] To: {phone_number} | Message: {message}")
        print(f"\n>>>> SMS MOCKED \nTo: {phone_number}\nText: {message}\n")
        return True
        
    url = "https://www.fast2sms.com/dev/bulkV2"
    querystring = {
        "authorization": api_key,
        "message": message,
        "language": "english",
        "route": "q",
        "numbers": phone_number
    }
    headers = {'cache-control': "no-cache"}
    
    try:
        logging.info(f"Attempting API SMS to {phone_number}...")
        response = requests.request("GET", url, headers=headers, params=querystring, timeout=5)
        
        if response.status_code == 200:
            logging.info(f"Successfully delivered SMS to {phone_number}")
            return True
        else:
            logging.error(f"Failed to Send SMS: {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Network Error sending SMS to {phone_number}: {str(e)}")
        return False
