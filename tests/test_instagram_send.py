from button_flow_service import get_menu_for_stage
from instagram_service import send_instagram_menu


recipient_id = "877021928624714"

menu = get_menu_for_stage(
    "WELCOME"
)

result = send_instagram_menu(
    recipient_id=recipient_id,
    menu=menu,
)

print(result)