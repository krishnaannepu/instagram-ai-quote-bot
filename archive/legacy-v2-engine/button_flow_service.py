# ------------------------------------------------------------------
# Button Flow Stages
# ------------------------------------------------------------------

STAGE_WELCOME = "WELCOME"
STAGE_SELECT_SERVICE = "SELECT_SERVICE"
STAGE_SELECT_PACKAGE = "SELECT_PACKAGE"
STAGE_SELECT_COVERAGE = "SELECT_COVERAGE"
STAGE_SELECT_TRAVEL = "SELECT_TRAVEL"
STAGE_SELECT_DURATION = "SELECT_DURATION"
STAGE_ENTER_EVENT_DATE = "ENTER_EVENT_DATE"
STAGE_ENTER_LOCATION = "ENTER_LOCATION"
STAGE_READY_FOR_QUOTE = "READY_FOR_QUOTE"
STAGE_ASK_EMAIL_CONFIRMATION = "ASK_EMAIL_CONFIRMATION"
STAGE_ENTER_CUSTOMER_EMAIL = "ENTER_CUSTOMER_EMAIL"
STAGE_POST_QUOTE_OPTIONS = "POST_QUOTE_OPTIONS"
STAGE_HUMAN_HANDOFF = "HUMAN_HANDOFF"
STAGE_ENTER_CALLBACK_PHONE = "ENTER_CALLBACK_PHONE"
STAGE_SELECT_CALLBACK_PREFERENCE = "SELECT_CALLBACK_PREFERENCE"
STAGE_FAQ = "FAQ"
STAGE_COMPLETED = "COMPLETED"

MAIN_MENU = {
    "message": "Welcome! How can we help you?",
    "options": [
        {"title": "Get a Quote", "payload": "GET_QUOTE"},
        {"title": "Speak to Team", "payload": "SPEAK_TO_TEAM"},
    ],
}

SERVICE_MENU = {
    "message": "Which service would you like?",
    "options": [
        {"title": "Wedding", "payload": "SERVICE_WEDDING"},
        {"title": "Birthday", "payload": "SERVICE_BIRTHDAY"},
        {"title": "Portrait", "payload": "SERVICE_PORTRAIT"},
        {"title": "Other Event", "payload": "SERVICE_EVENT"},
    ],
}

PACKAGE_MENU = {
    "message": "Which package would you like?",
    "options": [
        {"title": "Basic", "payload": "PACKAGE_BASIC"},
        {"title": "Premium", "payload": "PACKAGE_PREMIUM"},
    ],
}

COVERAGE_MENU = {
    "message": "What coverage do you need?",
    "options": [
        {"title": "Photography", "payload": "COVERAGE_PHOTOGRAPHY"},
        {"title": "Videography", "payload": "COVERAGE_VIDEOGRAPHY"},
        {"title": "Both", "payload": "COVERAGE_BOTH"},
    ],
}

TRAVEL_MENU = {
    "message": "Is travel required?",
    "options": [
        {"title": "Yes", "payload": "TRAVEL_YES"},
        {"title": "No", "payload": "TRAVEL_NO"},
    ],
}

EMAIL_CONFIRMATION_MENU = {
    "message": "Would you like a copy of your quote sent to your email?",
    "options": [
        {"title": "Yes", "payload": "EMAIL_YES"},
        {"title": "No", "payload": "EMAIL_NO"},
    ],
}

POST_QUOTE_MENU = {
    "message": "What would you like to do next?",
    "options": [
        {"title": "Speak to Team", "payload": "SPEAK_TO_TEAM"},
        {"title": "Start New Quote", "payload": "START_NEW_QUOTE"},
        {"title": "Finish", "payload": "FINISH"},
    ],
}

HANDOFF_ACTION_MENU = {
    "message": "How would you like to continue?",
    "options": [
        {"title": "Request Callback", "payload": "REQUEST_CALLBACK"},
        {"title": "Start New Quote", "payload": "START_NEW_QUOTE"},
        {"title": "Finish", "payload": "FINISH"},
    ],
}

CALLBACK_PREFERENCE_MENU = {
    "message": "When would you prefer us to call you?",
    "options": [
        {"title": "ASAP", "payload": "CALLBACK_ASAP"},
        {"title": "Morning", "payload": "CALLBACK_MORNING"},
        {"title": "Afternoon", "payload": "CALLBACK_AFTERNOON"},
    ],
}


def get_menu_for_stage(stage: str):
    if stage == STAGE_WELCOME:
        return MAIN_MENU
    if stage == STAGE_SELECT_SERVICE:
        return SERVICE_MENU
    if stage == STAGE_SELECT_PACKAGE:
        return PACKAGE_MENU
    if stage == STAGE_SELECT_COVERAGE:
        return COVERAGE_MENU
    if stage == STAGE_SELECT_TRAVEL:
        return TRAVEL_MENU
    if stage == STAGE_SELECT_DURATION:
        return {"message": "How many hours of coverage do you need?", "options": []}
    if stage == STAGE_ENTER_EVENT_DATE:
        return {"message": "What is the event date?", "options": []}
    if stage == STAGE_ENTER_LOCATION:
        return {"message": "Where will the event take place?", "options": []}
    if stage == STAGE_READY_FOR_QUOTE:
        return {"message": "Your quote details are ready.", "options": []}
    if stage == STAGE_ASK_EMAIL_CONFIRMATION:
        return EMAIL_CONFIRMATION_MENU
    if stage == STAGE_ENTER_CUSTOMER_EMAIL:
        return {
            "message": "Please enter the email address where you would like us to send your quote.",
            "options": [],
        }
    if stage == STAGE_POST_QUOTE_OPTIONS:
        return POST_QUOTE_MENU
    if stage == STAGE_HUMAN_HANDOFF:
        return HANDOFF_ACTION_MENU
    if stage == STAGE_ENTER_CALLBACK_PHONE:
        return {
            "message": "Please enter the phone number you would like us to call.",
            "options": [],
        }
    if stage == STAGE_SELECT_CALLBACK_PREFERENCE:
        return CALLBACK_PREFERENCE_MENU
    if stage == STAGE_FAQ:
        return {"message": "Please send your question.", "options": []}
    if stage == STAGE_COMPLETED:
        return {
            "message": "Thank you for contacting us. We look forward to helping with your event.",
            "options": [],
        }
    return MAIN_MENU
