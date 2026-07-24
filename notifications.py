import flet as ft
import json
import os
import requests
import threading
from datetime import datetime

# UI Constants
BG_COLOR = "#0D0D0D"
CARD_COLOR = "#1A1A1A"
ACCENT_GREEN = ft.colors.LIME_600
TEXT_COLOR = ft.colors.GREY_200
FIREBASE_URL = "https://alwafa-afcc1-default-rtdb.firebaseio.com/noti.json"
NOTIFICATIONS_FILE = "notifications.json"
COUNT_FILE = "last_count.json"


class NotificationCard(ft.Container):
    """Component for displaying individual notification items with encapsulation."""
    def __init__(self, text, amount, notif_type, date, img_url, is_bank, notif_key, page: ft.Page, refresh_callback):
        super().__init__()
        self.text = text
        self.amount = amount
        self.notif_type = notif_type
        self.date = date
        self.img_url = img_url
        self.is_bank = is_bank
        self.notif_key = notif_key
        self.page_ref = page
        self.refresh_callback = refresh_callback
        
        self.bg_color = CARD_COLOR
        self.border_radius = 15
        self.margin = ft.margin.only(bottom=8)
        self.padding = ft.padding.all(12)
        
        self.build_card_ui()

    def get_type_config(self):
        """Returns visual configurations according to notification type."""
        configs = {
            "w": {"text": f"سحب {self.amount:,.0f}", "color": "#c94559", "icon": ft.icons.CALL_MADE},
            "d": {"text": f"إيداع {self.amount:,.0f}", "color": ACCENT_GREEN, "icon": ft.icons.CALL_RECEIVED},
            "don": {"text": f"تبرع بمبلغ {self.amount:,.0f}", "color": ft.colors.TEAL_100, "icon": ft.icons.MONETIZATION_ON},
            "s": {"text": "مشترك جديد", "color": "#79a995", "icon": ft.icons.PERSON_ADD_ALT_1},
            "u": {"text": "إنسحاب مشترك", "color": "#e56328", "icon": ft.icons.PERSON_REMOVE_ALT_1}
        }
        return configs.get(self.notif_type, {"text": "إشعار عام", "color": "#BDBDBD", "icon": ft.icons.NOTIFICATIONS_OUTLINED})

    def open_image_in_browser(self, e):
        """Launches the image URL in external browser."""
        if self.img_url and self.img_url.strip():
            self.page_ref.launch_url(self.img_url.strip())

    def delete_notification(self, e):
        """Worker method to handle asynchronous deleting via requests."""
        def delete_worker():
            try:
                del_url = f"https://alwafa-afcc1-default-rtdb.firebaseio.com/noti/{self.notif_key}.json"
                res = requests.delete(del_url, timeout=10)
                if res.status_code == 200:
                    if os.path.exists(NOTIFICATIONS_FILE):
                        try:
                            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                                local_data = json.load(f)
                            if self.notif_key in local_data:
                                del local_data[self.notif_key]
                            with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                                json.dump(local_data, f, ensure_ascii=False, indent=4)
                        except Exception:
                            pass
                    self.refresh_callback()
            except Exception as ex:
                print(f"Error deleting notification: {ex}")

        threading.Thread(target=delete_worker, daemon=True).start()

    def edit_notification(self, e):
        """Opens dialog to update existing notification content and optional image URL."""
        desc_input = ft.TextField(label="الوصف", value=self.text, multiline=True)
        show_amount = self.notif_type in ["w", "d", "don"]
        amount_input = ft.TextField(label="المبلغ", value=str(self.amount), keyboard_type=ft.KeyboardType.NUMBER, visible=show_amount)
        
        show_img = self.notif_type in ["n", "don", "d"]
        
        # Dropdown placed before img_input
        img_type_dropdown = ft.Dropdown(
            label="نوع الصورة",
            options=[
                ft.dropdown.Option("bank", "إشعار بنكك"),
                ft.dropdown.Option("normal", "صورة عادية"),
            ],
            value="bank" if self.is_bank else "normal",
            visible=show_img
        )
        img_input = ft.TextField(label="رابط الصورة (اختياري)", value=self.img_url if self.img_url else "", visible=show_img)

        if self.notif_type == "n":
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
                "date": self.date,
                "noti": desc_input.value.strip(),
                "type": self.notif_type,
                "img": img_input.value.strip() if show_img else "",
                "bank": (img_type_dropdown.value == "bank") if show_img else False
            }

            def edit_worker():
                try:
                    edit_url = f"https://alwafa-afcc1-default-rtdb.firebaseio.com/noti/{self.notif_key}.json"
                    res = requests.patch(edit_url, json=payload, timeout=10)
                    if res.status_code == 200:
                        if os.path.exists(NOTIFICATIONS_FILE):
                            try:
                                with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                                    local_data = json.load(f)
                                if self.notif_key in local_data:
                                    local_data[self.notif_key].update(payload)
                                with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                                    json.dump(local_data, f, ensure_ascii=False, indent=4)
                            except Exception:
                                pass
                        self.refresh_callback()
                except Exception as ex:
                    print(f"Error editing notification: {ex}")

            self.page_ref.dialog.open = False
            self.page_ref.update()
            threading.Thread(target=edit_worker, daemon=True).start()

        dialog = ft.AlertDialog(
            title=ft.Text("تعديل الإشعار", text_align="right", size=16),
            content=ft.Column(controls=[desc_input, amount_input, img_type_dropdown, img_input], tight=True, spacing=15),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(self.page_ref.dialog, "open", False) or self.page_ref.update()),
                ft.TextButton("حفظ التعديل", on_click=save_edit)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page_ref.dialog = dialog
        dialog.open = True
        self.page_ref.update()

    def build_card_ui(self):
        """Builds UI elements layout for the card component."""
        config = self.get_type_config()
        
        column_controls = [
            ft.Text(config["text"], color=TEXT_COLOR, weight=ft.FontWeight.BOLD, size=15),
            ft.Text(self.text, color="#9E9E9E", size=14)
        ]

        # Add "اشعار بنكك" or Image button compatible with Flet 0.19.0
        if self.img_url and self.img_url.strip():
            if self.is_bank == True:
            	btn_label = "إشعار بنكك"
            	btn_col = ft.colors.LIME_600
            	btn_icon = "check_circle"
            else:
            	btn_label = "عرض الصورة"
            	btn_col = ft.colors.ORANGE_100
            	btn_icon = "image"
            column_controls.append(
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(btn_icon, color=btn_col, size=16),
                            ft.Text(btn_label, color=btn_col, size=12)
                        ],
                        tight=True,
                        spacing=4
                    ),
                    style=ft.ButtonStyle(padding=0),
                    on_click=self.open_image_in_browser
                )
            )

        column_controls.append(ft.Text("في يوم " + self.date, color="#616161", size=12))

        self.content = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(config["icon"], color=config["color"], size=22),
                    padding=10,
                    bgcolor="#323232",
                    border_radius=12
                ),
                ft.Column(
                    controls=column_controls,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=2,
                    tight=True,
                    expand=True
                ),
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.icons.EDIT_ROUNDED, 
                            icon_color=ft.colors.GREY_400, 
                            icon_size=18, 
                            on_click=self.edit_notification, 
                            tooltip="تعديل"
                        ),
                        ft.IconButton(
                            icon=ft.icons.DELETE_ROUNDED, 
                            icon_color=ft.colors.RED_300, 
                            icon_size=18, 
                            on_click=self.delete_notification, 
                            tooltip="مسح"
                        )
                    ],
                    visible=True,
                    tight=True,
                    spacing=0
                )
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START
        )


class AddNotificationDialog:
    """Class wrapper for adding new notification items with optional image field."""
    def __init__(self, page: ft.Page, refresh_callback):
        self.page = page
        self.refresh_callback = refresh_callback
        
        self.noti_type_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("n", "إشعار عام"),
                ft.dropdown.Option("don", "اشعار تبرع"),
            ],
            value="n"
        )
        self.desc_input = ft.TextField(label="الوصف", max_length=100, multiline=True)
        self.amount_input = ft.TextField(label="المبلغ", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
        
        # Dropdown placed above img_input
        self.img_type_dropdown = ft.Dropdown(
            label="نوع الصورة",
            options=[
                ft.dropdown.Option("bank", "إشعار بنكك"),
                ft.dropdown.Option("normal", "صورة عادية"),
            ],
            value="bank",
            visible=True
        )
        self.img_input = ft.TextField(label="رابط الصورة (اختياري)", visible=True)

        self.noti_type_dropdown.on_change = self.on_type_changed

    def on_type_changed(self, e):
        """Toggles inputs according to notification type selection."""
        if self.noti_type_dropdown.value == "n":
            self.amount_input.visible = False
            self.desc_input.max_length = 100
        else:
            self.amount_input.visible = True
            self.desc_input.max_length = None
        self.img_type_dropdown.visible = True
        self.img_input.visible = True
        self.page.dialog.update()

    def submit_notification(self, e):
        """Processes posting input payload to Firebase RTDB."""
        if not self.desc_input.value.strip():
            return

        selected_type = self.noti_type_dropdown.value
        final_amount = 0

        if selected_type != "n":
            try:
                final_amount = float(self.amount_input.value.strip())
            except ValueError:
                final_amount = 0

        is_bank_val = (self.img_type_dropdown.value == "bank")

        payload = {
            "amount": final_amount,
            "date": datetime.now().strftime("%d-%m-%Y"),
            "noti": self.desc_input.value.strip(),
            "type": selected_type,
            "img": self.img_input.value.strip(),
            "bank": is_bank_val
        }

        def upload_worker():
            try:
                res = requests.post(FIREBASE_URL, json=payload, timeout=10)
                if res.status_code == 200:
                    self.refresh_callback()
            except Exception as ex:
                print(f"Error posting notification: {ex}")

        self.page.dialog.open = False
        self.page.update()
        threading.Thread(target=upload_worker, daemon=True).start()

    def show(self):
        """Displays modal view dialog."""
        dialog = ft.AlertDialog(
            title=ft.Text("إضافة إشعار جديد", text_align="right", size=16),
            content=ft.Column(
                controls=[
                    self.noti_type_dropdown, 
                    self.desc_input, 
                    self.amount_input, 
                    self.img_type_dropdown,
                    self.img_input
                ],
                tight=True,
                spacing=15
            ),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.TextButton("إرسال الإشعار", on_click=self.submit_notification)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()


class NotificationsViewManager:
    """Manages notifications view state, fetching and robust multi-format date sorting."""
    def __init__(self, page: ft.Page):
        self.page = page
        self.notif_list = ft.ListView(expand=True, spacing=5, padding=0)
        self.loading_ring = ft.ProgressRing(color=ft.colors.ORANGE_600)
        self.loading_container = ft.Container(content=self.loading_ring, alignment=ft.alignment.center, expand=True)
        self.view = ft.View("/notifications", bgcolor=BG_COLOR, padding=12, controls=[self.loading_container])

    def parse_date_robustly(self, date_str):
        """Tries multiple date parsing patterns to prevent invalid sorting offsets."""
        if not date_str:
            return datetime.min
        formats = ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return datetime.min

    def fetch_data(self):
        """Fetches notification records and sorts them seamlessly from newest to oldest."""
        total_deposit, total_withdraw = 0, 0
        local_data = {}

        if os.path.exists(NOTIFICATIONS_FILE):
            try:
                with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                    local_data = json.load(f) or {}
            except Exception:
                local_data = {}

        try:
            response = requests.get(FIREBASE_URL, timeout=5)
            if response.status_code == 200:
                server_data = response.json()
                if isinstance(server_data, dict):
                    for k, v in server_data.items():
                        if k not in local_data:
                            local_data[k] = v
                elif isinstance(server_data, list):
                    for idx, v in enumerate(server_data):
                        k = f"server_{idx}"
                        if v and k not in local_data:
                            local_data[k] = v

                with open(COUNT_FILE, "w") as f:
                    json.dump(len(local_data), f)
                with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(local_data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

        if local_data:
            items = []
            for k, v in local_data.items():
                if v and isinstance(v, dict):
                    noti_text = v.get('noti', '').strip()
                    if not noti_text and not v.get('type'):
                        continue
                    date_str = v.get('date', '')
                    parsed_date = self.parse_date_robustly(date_str)
                    items.append((parsed_date, k, v))

            # Sort items dynamically from newest to oldest
            items.sort(key=lambda x: x[0], reverse=True)

            self.notif_list.controls.clear()
            for _, key, item in items:
                self.notif_list.controls.append(
                    NotificationCard(
                        text=item.get('noti', ''),
                        amount=item.get('amount', 0),
                        notif_type=item.get('type'),
                        date=item.get('date', ''),
                        img_url=item.get('img', ''),
                        is_bank=item.get('bank', False),
                        notif_key=key,
                        page=self.page,
                        refresh_callback=self.fetch_data
                    )
                )
                if item.get("type") == "d":
                    total_deposit += item.get("amount", 0)
                elif item.get("type") == "w":
                    total_withdraw += item.get("amount", 0)

        header = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.alignment.bottom_left, 
                end=ft.alignment.top_right, 
                colors=["#211111", "#222822"]
            ),
            content=ft.Row([
                ft.Column([
                    ft.Text("إجمالي الودائع", color=ACCENT_GREEN, size=14), 
                    ft.Text(f"{total_deposit:,.0f}", color=ACCENT_GREEN, size=20, weight=ft.FontWeight.BOLD)
                ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ft.VerticalDivider(width=1, color="#333333"),
                ft.Column([
                    ft.Text("إجمالي السحب", color="#c94559", size=14), 
                    ft.Text(f"{total_withdraw:,.0f}", color="#c94559", size=20, weight=ft.FontWeight.BOLD)
                ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ]), 
            padding=15, 
            bgcolor=CARD_COLOR, 
            border_radius=20, 
            margin=ft.margin.only(top=0, bottom=5)
        )

        action_buttons = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.FloatingActionButton(
                    icon=ft.icons.ADD_ROUNDED,
                    bgcolor=ft.colors.ORANGE_600,
                    on_click=lambda e: AddNotificationDialog(self.page, self.fetch_data).show(),
                    width=40,
                    height=40,
                    tooltip="إضافة إشعار جديد"
                ),
                ft.FloatingActionButton(
                    icon=ft.icons.ARROW_FORWARD,
                    bgcolor=ft.colors.GREY_800,
                    on_click=lambda _: self.page.go("/"),
                    width=40,
                    height=40,
                    tooltip="رجوع"
                )
            ]
        )

        self.view.controls = [
            header,
            self.notif_list,
            action_buttons
        ]
        self.page.update()

    def get_view(self):
        """Starts asynchronous fetch and returns Flet View instance."""
        threading.Thread(target=self.fetch_data, daemon=True).start()
        return self.view


def get_notifications_view(page: ft.Page):
    """Factory helper function returning notification view."""
    manager = NotificationsViewManager(page)
    return manager.get_view()


def show_add_notification_dialog(page: ft.Page, refresh_callback):
    """Helper dialog launcher function."""
    dialog_instance = AddNotificationDialog(page, refresh_callback)
    dialog_instance.show()


def build_notification_icon(page: ft.Page):
    """Generates badged notification icon stack for navigation bar."""
    try:
        res = requests.get(FIREBASE_URL, timeout=3).json()
        server_count = len(res) if res else 0
    except Exception:
        server_count = 0

    local_count = 0
    if os.path.exists(NOTIFICATIONS_FILE):
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                local_count = len(data) if data else 0
        except Exception:
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
        ft.IconButton(
            icon=ft.icons.NOTIFICATIONS, 
            icon_color=ft.colors.GREY_400, 
            on_click=lambda _: page.go("/notifications")
        ),
        ft.Container(
            content=ft.CircleAvatar(bgcolor=ft.colors.RED, radius=5), 
            visible=has_new, 
            top=5, 
            right=5
        )
    ])
