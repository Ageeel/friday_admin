import flet as ft
import json
import os
import requests
import threading
from datetime import datetime

# init variables
BG_COLOR = "#0D0D0D"
CARD_COLOR = "#1A1A1A"
ACCENT_GREEN = ft.colors.LIME_600
TEXT_COLOR = ft.colors.GREY_200
FIREBASE_URL = "https://alwafa-afcc1-default-rtdb.firebaseio.com/noti.json"
NOTIFICATIONS_FILE = "notifications.json"
COUNT_FILE = "last_count.json"

def notification_card(text, amount, type, date, notif_key, page, refresh_callback):
    config = {
        "w": {"text": f"سحب {amount:,.0f}", "color": "#c94559", "icon": ft.icons.CALL_MADE},
        "d": {"text": f"إيداع {amount:,.0f}", "color": ACCENT_GREEN, "icon": ft.icons.CALL_RECEIVED},
        "don":{"text": f"تبرع بمبلغ {amount:,.0f}", "color": ft.colors.TEAL_100,"icon": ft.icons.MONETIZATION_ON},
        "s": {"text": "مشترك جديد", "color": "#79a995", "icon": ft.icons.PERSON_ADD_ALT_1},
        "u": {"text": "إنسحاب مشترك", "color": "#e56328", "icon": ft.icons.PERSON_REMOVE_ALT_1}
    }.get(type, {"text": "إشعار عام", "color": "#BDBDBD", "icon": ft.icons.NOTIFICATIONS_OUTLINED})

    def delete_notification(e):
        def delete_worker():
            try:
                # Delete specific key from Firebase
                del_url = f"https://alwafa-afcc1-default-rtdb.firebaseio.com/noti/{notif_key}.json"
                res = requests.delete(del_url, timeout=10)
                if res.status_code == 200:
                    # Remove from local file cache to prevent phantom loading
                    if os.path.exists(NOTIFICATIONS_FILE):
                        try:
                            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                                local_data = json.load(f)
                            if notif_key in local_data:
                                del local_data[notif_key]
                            with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                                json.dump(local_data, f, ensure_ascii=False, indent=4)
                        except:
                            pass
                    refresh_callback()
            except Exception as ex:
                print(f"Error deleting notification: {ex}")
        
        threading.Thread(target=delete_worker, daemon=True).start()

    def edit_notification(e):
        desc_input = ft.TextField(label="الوصف", value=text, multiline=True)
        # Show amount input if the notification type carries a balance amount
        show_amount = type in ["w", "d", "don"]
        amount_input = ft.TextField(label="المبلغ", value=str(amount), keyboard_type=ft.KeyboardType.NUMBER, visible=show_amount)
        
        if type == "n":
            desc_input.max_length = 100

        def save_edit(ev):
            if not desc_input.value.strip():
                return
            
            final_amount = 0
            if show_amount:
                try:
                    final_amount = float(amount_input.value.strip())
                except ValueError:
                    final_amount = 0

            payload = {
                "amount": final_amount,
                "date": date,
                "noti": desc_input.value.strip(),
                "type": type
            }

            def edit_worker():
                try:
                    edit_url = f"https://alwafa-afcc1-default-rtdb.firebaseio.com/noti/{notif_key}.json"
                    res = requests.patch(edit_url, json=payload, timeout=10)
                    if res.status_code == 200:
                        # Update local cache directly
                        if os.path.exists(NOTIFICATIONS_FILE):
                            try:
                                with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                                    local_data = json.load(f)
                                if notif_key in local_data:
                                    local_data[notif_key].update(payload)
                                with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                                    json.dump(local_data, f, ensure_ascii=False, indent=4)
                            except:
                                pass
                        refresh_callback()
                except Exception as ex:
                    print(f"Error editing notification: {ex}")

            page.dialog.open = False
            page.update()
            threading.Thread(target=edit_worker, daemon=True).start()

        dialog = ft.AlertDialog(
            title=ft.Text("تعديل الإشعار", text_align="right", size=16),
            content=ft.Column(controls=[desc_input, amount_input], tight=True, spacing=15),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(page.dialog, "open", False) or page.update()),
                ft.TextButton("حفظ التعديل", on_click=save_edit)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        page.dialog = dialog
        dialog.open = True
        page.update()

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(config["icon"], color=config["color"], size=22),
                    padding=10,
                    bgcolor="#323232",
                    border_radius=12
                ),
                ft.Column(
                    controls=[
                        ft.Text(config["text"], color=TEXT_COLOR, weight=ft.FontWeight.BOLD, size=15),
                        ft.Text(text, color="#9E9E9E", size=14),
                        ft.Text("في يوم " + date, color="#616161", size=12)
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                    expand=True
                ),
                # Action buttons are now universally visible for all notifications
                ft.Row(
                    controls=[
                        ft.IconButton(icon=ft.icons.EDIT_ROUNDED, icon_color=ft.colors.GREY_400, icon_size=18, on_click=edit_notification, tooltip="تعديل"),
                        ft.IconButton(icon=ft.icons.DELETE_ROUNDED, icon_color=ft.colors.RED_300, icon_size=18, on_click=delete_notification, tooltip="مسح")
                    ],
                    visible=True,
                    tight=True,
                    spacing=0
                )
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START
        ),
        padding=ft.padding.only(right=10, left=10, top=10, bottom=15),
        bgcolor=CARD_COLOR,
        border_radius=15,
        margin=ft.margin.only(bottom=10)
    )

def get_notifications_view(page: ft.Page):
    notif_list = ft.ListView(expand=True, spacing=0)
    loading_ring = ft.ProgressRing(color=ft.colors.ORANGE_600)
    loading_container = ft.Container(content=loading_ring, alignment=ft.alignment.center, expand=True)
    
    view = ft.View("/notifications", bgcolor=BG_COLOR, padding=20, controls=[loading_container])

    def fetch_data():
        total_deposit, total_withdraw = 0, 0
        
        # Load existing local notifications first to prevent them from being overwritten
        local_data = {}
        if os.path.exists(NOTIFICATIONS_FILE):
            try:
                with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                    local_data = json.load(f) or {}
            except:
                local_data = {}

        try:
            response = requests.get(FIREBASE_URL, timeout=5)
            if response.status_code == 200:
                server_data = response.json()
                if isinstance(server_data, dict):
                    # Merge server notifications into local notifications seamlessly
                    for k, v in server_data.items():
                        if k not in local_data:
                            local_data[k] = v
                elif isinstance(server_data, list):
                    # Handle if server data is a list instead of a dict
                    for idx, v in enumerate(server_data):
                        k = f"server_{idx}"
                        if v and k not in local_data:
                            local_data[k] = v

                # Update the cache counters and file records safely
                with open(COUNT_FILE, "w") as f: 
                    json.dump(len(local_data), f)
                with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f: 
                    json.dump(local_data, f, ensure_ascii=False, indent=4)
        except:
            # Fallback directly to local data if network request fails completely
            pass

        if local_data:
            # Convert dictionary into a list of items for robust sorting
            items = []
            for k, v in local_data.items():
                if v:
                    date_str = v.get('date', '')
                    try:
                        parsed_date = datetime.strptime(date_str, "%d-%m-%Y")
                    except:
                        parsed_date = datetime.min
                    items.append((parsed_date, k, v))

            # Sort items dynamically by chronological order (Newest first)
            items.sort(key=lambda x: x[0], reverse=True)

            # Append sorted layout widgets directly into our UI list container
            notif_list.controls.clear()
            for _, key, item in items:
                notif_list.controls.append(
                    notification_card(
                        item.get('noti', ''), 
                        item.get('amount', 0), 
                        item.get('type'), 
                        item.get('date', ''),
                        key,
                        page,
                        fetch_data
                    )
                )
                if item.get("type") == "d": total_deposit += item.get("amount", 0)
                elif item.get("type") == "w": total_withdraw += item.get("amount", 0)
        
        header = ft.Container(gradient=ft.LinearGradient(begin=ft.alignment.bottom_left, end=ft.alignment.top_right, colors=["#211111", "#222822"]),
        content=ft.Row([
            ft.Column([ft.Text("إجمالي الودائع", color=ACCENT_GREEN, size=14), ft.Text(f"{total_deposit:,.0f}", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD)], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.VerticalDivider(width=1, color="#333333"),
            ft.Column([ft.Text("إجمالي السحب", color="#c94559", size=14), ft.Text(f"{total_withdraw:,.0f}", color="#c94559", size=20, weight=ft.FontWeight.BOLD)], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        ]), padding=20, bgcolor=CARD_COLOR, border_radius=20, margin=ft.margin.only(top=30))
        
        # Horizontal action row at the bottom of the page layout
        action_buttons = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[                
                ft.FloatingActionButton(
                    icon=ft.icons.ADD_ROUNDED, 
                    bgcolor=ft.colors.ORANGE_600, 
                    on_click=lambda e: show_add_notification_dialog(page, fetch_data),
                    width=40, 
                    height=40,
                    tooltip="إضافة إشعار جديد"
                ),
                ft.FloatingActionButton(
                    icon=ft.icons.ARROW_FORWARD, 
                    bgcolor=ft.colors.GREY_800,
                    on_click=lambda _: page.go("/"), 
                    width=40, 
                    height=40,
                    tooltip="رجوع"
                )
            ]
        )

        view.controls = [header, notif_list, action_buttons]
        page.update()

    threading.Thread(target=fetch_data, daemon=True).start()
    return view

def show_add_notification_dialog(page: ft.Page, refresh_callback):
    """Dialog creation class wrapper logic to prompt managers for appending structural notifications"""
    noti_type_dropdown = ft.Dropdown(
        options=[
            ft.dropdown.Option("n", "إشعار عام"),
            ft.dropdown.Option("don", "اشعار تبرع"),
        ],
        value="n"
    )
    
    desc_input = ft.TextField(
        label="الوصف", 
        max_length=100, 
        multiline=True
    )
    
    amount_input = ft.TextField(
        label="المبلغ", 
        keyboard_type=ft.KeyboardType.NUMBER, 
        visible=False
    )

    def on_type_changed(e):
        if noti_type_dropdown.value == "n":
            amount_input.visible = False
            desc_input.max_length = 100
        else:
            amount_input.visible = True
            desc_input.max_length = None
        page.dialog.update()

    noti_type_dropdown.on_change = on_type_changed

    def submit_notification(e):
        if not desc_input.value.strip():
            return
        
        selected_type = noti_type_dropdown.value
        final_amount = 0
        
        if selected_type != "n":
            try:
                final_amount = float(amount_input.value.strip())
            except ValueError:
                final_amount = 0

        payload = {
            "amount": final_amount,
            "date": datetime.now().strftime("%d-%m-%Y"),
            "noti": desc_input.value.strip(),
            "type": selected_type
        }

        def upload_worker():
            try:
                res = requests.post(FIREBASE_URL, json=payload, timeout=10)
                if res.status_code == 200:
                    refresh_callback()
            except Exception as ex:
                print(f"Error posting notification: {ex}")

        page.dialog.open = False
        page.update()
        threading.Thread(target=upload_worker, daemon=True).start()

    dialog = ft.AlertDialog(
        title=ft.Text("إضافة إشعار جديد", text_align="right", size=16),
        content=ft.Column(
            controls=[noti_type_dropdown, desc_input, amount_input],
            tight=True,
            spacing=15
        ),
        actions=[
            ft.TextButton("إلغاء", on_click=lambda _: setattr(page.dialog, "open", False) or page.update()),
            ft.TextButton("إرسال الإشعار", on_click=submit_notification)
        ],
        actions_alignment=ft.MainAxisAlignment.END
    )
    
    page.dialog = dialog
    dialog.open = True
    page.update()

def build_notification_icon(page):
    try:
        res = requests.get(FIREBASE_URL, timeout=3).json()
        server_count = len(res) if res else 0
    except: 
        server_count = 0
        
    local_count = 0
    if os.path.exists(NOTIFICATIONS_FILE):
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                local_count = len(data) if data else 0
        except:
            local_count = 0
            
    saved_count = 0
    if os.path.exists(COUNT_FILE):
        try:
            with open(COUNT_FILE, "r") as f:
                content = f.read()
                if content:
                    saved_count = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            saved_count = 0
            
    has_new = max(server_count, local_count) > saved_count
    return ft.Stack([
        ft.IconButton(icon=ft.icons.NOTIFICATIONS,icon_color=ft.colors.GREY_400, on_click=lambda _: page.go("/notifications")),
        ft.Container(content=ft.CircleAvatar(bgcolor=ft.colors.RED, radius=5), visible=has_new, top=5, right=5)
    ])
