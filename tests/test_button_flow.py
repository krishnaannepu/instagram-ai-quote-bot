from button_flow_service import get_menu_for_stage


stages = [
    "WELCOME",
    "SELECT_SERVICE",
    "SELECT_PACKAGE",
    "SELECT_COVERAGE",
    "SELECT_TRAVEL",
    "SELECT_DURATION",
    "ENTER_EVENT_DATE",
    "ENTER_LOCATION",
    "READY_FOR_QUOTE",
]


for stage in stages:
    print()
    print("STAGE:", stage)
    print(get_menu_for_stage(stage))