import flet as ft
import requests
import json
import os
from datetime import datetime

# Import the helper function from custom local module
from last_friday import get_last_fr

# --- Constants ---
DB_URL_BASE = "https://alwafa-afcc1-default-rtdb.firebaseio.com/sub"
FIREBASE_NOTI_URL = "https://alwafa-afcc1-default-rtdb.firebaseio.com/noti.json"
CACHE_FILE = os.path.join(os.path.expanduser(""), "data_cache.json")
START_DATE = datetime(2026, 6, 12)

# --- Imported Components ---
from notifications import get_notifications_view, build_notification_icon


class SubscriptionApp:
    """Main application class encapsulating logic and user interface components."""
    def __init__(self, page: ft.Page):
        self.page = page
        self.all_data = {}
        self.total_fridays = (datetime.now() - START_DATE).days // 7
        
        # UI lists for tabs navigation
        self.active_members_list = ft.ListView(expand=True, spacing=0)
        self.retracted_members_list = ft.ListView(expand=True, spacing=0)
        
        # Tabs control for switching active/retracted views
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            unselected_label_color="white",
            tabs=[
                ft.Tab(text="المشتركين الحاليين", content=self.active_members_list),
                ft.Tab(text="قائمة المنسحبين", content=self.retracted_members_list),
            ],
            expand=True
        )
        
        self.total_balance_text_header = ft.Text("0", size=16, weight="bold", color=ft.colors.ORANGE_600)
        self.total_balance_text_body = ft.Text("0", size=16, weight="bold", color=ft.colors.WHITE)
        self.total_retracted = ft.Text("0", size=16, weight="bold", color=ft.colors.WHITE)
        
        self.loading_overlay = ft.Container(
            visible=False,
            bgcolor=ft.colors.with_opacity(0.8, ft.colors.BLACK),
            alignment=ft.alignment.center,
            expand=True,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(),
                    ft.Text("جار التحميل، إنتظر قليلا", color=ft.colors.WHITE, size=16, weight="bold")
                ]
            )
        )
        
        self.onboarding_container = ft.Container(
            visible=False, 
            bgcolor=ft.colors.BLACK, 
            alignment=ft.alignment.center, 
            expand=True, 
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER, 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                controls=[
                    ft.Icon(ft.icons.WALLET, size=60, color=ft.colors.ORANGE_400), 
                    ft.Text("نحول مدخراتنا الأسبوعية لفرصة إستثمارية حقيقية. يلا إشترك معانا والتزم بـ 1,000 جنيه كل يوم جمعة، كل دا عشان نسوي راس مال ، ونخطط لمشروع يخدمنا في المستقبل ويرفع مكانة الأسرة", size=20, color=ft.colors.GREY_300, text_align=ft.TextAlign.CENTER), 
                    ft.Text("أكبر إدخار أسري أسبوعي", size=16, color="grey", text_align=ft.TextAlign.CENTER), 
                    ft.Container(height=15), 
                    ft.ElevatedButton("ابدأ الاستخدام", on_click=self.close_onboarding, style=ft.ButtonStyle(bgcolor=ft.colors.ORANGE_600, color=ft.colors.BLACK))
                ]
            )
        )
        
        self.tools_section = ToolsComponent()
        self.search_field = ft.TextField(
            hint_text="ابحث عن اسم المشترك...",
            hint_style=ft.TextStyle(color=ft.colors.GREY_600, size=14),
            prefix_icon=ft.icons.SEARCH,
            bgcolor=ft.colors.GREY_900,
            color=ft.colors.WHITE,
            border=ft.InputBorder.NONE,
            border_radius=20,
            content_padding=14,
            on_change=lambda e: self.render_data(self.all_data, e.control.value)
        )
        
        self.add_member_button = ft.FloatingActionButton(
            icon=ft.icons.ADD,
            bgcolor=ft.colors.ORANGE_600,
            on_click=self.show_add_member_dialog,
            width=40,
            height=40,
            visible=False
        )

    def setup_page(self):
        """Initializes main page settings, theme and fonts."""
        self.page.title = "كل جمعة"
        self.page.rtl = True
        self.page.bgcolor = ft.colors.BLACK
        self.page.fonts = {"font": "font/ar.ttf"}
        self.page.theme = ft.Theme(font_family="font", color_scheme=ft.ColorScheme(primary=ft.colors.ORANGE_400))
        self.page.padding = 0
        self.page.on_route_change = self.route_change

    def get_total_amounts(self, type_str):
        """Retrieves total transaction amounts from remote Firebase or local file fallback."""
        total_amount = 0
        data = None
        try:
            res = requests.get(FIREBASE_NOTI_URL, timeout=5)
            if res.status_code == 200:
                data = res.json()
        except Exception:
            data = None

        if data is None and os.path.exists("notifications.json"):
            try:
                with open("notifications.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if data:
            items = data.values() if isinstance(data, dict) else data
            for val in items:
                if isinstance(val, dict) and val.get("type") == str(type_str):
                    total_amount += val.get("amount", 0)
        return total_amount

    def log_notification(self, type_char, text_content, amount_val=0):
        """Posts log notification item to Firebase using requests."""
        payload = {
            "amount": amount_val,
            "date": datetime.now().strftime("%d-%m-%Y"),
            "noti": text_content,
            "type": type_char
        }
        try:
            requests.post(FIREBASE_NOTI_URL, json=payload, timeout=10)
        except Exception as e:
            print(f"Error sending notification to Firebase: {e}")

    def show_finance_dialog(self, is_withdraw: bool):
        """Displays financial transaction modal dialog."""
        title_text = "سحب من أموال المشتركين" if is_withdraw else "إيداع أموال "
        amount_label = "المبلغ" if is_withdraw else "المبلغ "
        amount_in = ft.TextField(label=amount_label, keyboard_type=ft.KeyboardType.NUMBER)

        def confirm_transaction(e):
            try:
                amt = float(amount_in.value.strip())
                if amt <= 0: return
            except ValueError:
                return

            if is_withdraw:
                msg = f"تم سحب مبلغ {amt:,.0f} جنيه من اموال المشتركين"
                t_char = "w"
            else:
                msg = f"تم إيداع مبلغ {amt:,.0f} جنيه"
                t_char = "d"

            self.page.dialog.open = False
            self.show_loading(True)
            self.log_notification(type_char=t_char, text_content=msg, amount_val=amt)
            self.load_data()

        dialog = ft.AlertDialog(
            title=ft.Text(title_text, text_align="right", size=16),
            content=ft.Column(controls=[amount_in], tight=True, spacing=10),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.TextButton("تأكيد العملية", on_click=confirm_transaction)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_loading(self, status: bool):
        """Toggles full screen progress ring indicator overlay."""
        self.loading_overlay.visible = status
        self.page.update()

    def save_cache(self):
        """Saves active member state into local data cache file."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.all_data, f, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def load_data(self):
        """Asynchronously loads member data via HTTP request or local cache fallback."""
        self.show_loading(True)
        url = f"{DB_URL_BASE}.json"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                self.all_data = res.json() or {}
                self.save_cache()
                self.render_data(self.all_data)
        except Exception:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.all_data = json.load(f)
                self.render_data(self.all_data)
        self.show_loading(False)

    def update_member_db(self, member_id, payload):
        """Updates specific member record in Firebase using HTTP PATCH."""
        self.show_loading(True)
        url = f"{DB_URL_BASE}/{member_id}.json"
        try:
            res = requests.patch(url, json=payload, timeout=10)
            if res.status_code == 200:
                if member_id in self.all_data:
                    self.all_data[member_id].update(payload)
                self.save_cache()
                self.render_data(self.all_data)
        except Exception as ex:
            print(f"Error updating member: {ex}")
        finally:
            self.show_loading(False)

    def add_new_member_db(self, payload):
        """Posts new member payload record to Firebase database."""
        self.show_loading(True)
        url = f"{DB_URL_BASE}.json"
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                response_data = res.json()
                new_key = response_data.get("name") if response_data else None
                
                if new_key:
                    self.all_data[new_key] = payload
                else:
                    new_key = f"user_{int(datetime.now().timestamp())}"
                    self.all_data[new_key] = payload
                    
                self.save_cache()
                member_name = payload.get("name", "مجهول")
                self.log_notification(type_char="s", text_content=f"إشترك {member_name} واودع مبلغ 1000 جنيه")
                self.render_data(self.all_data)
        except Exception as ex:
            print(f"Error adding member: {ex}")
        finally:
            self.show_loading(False)

    def handle_quick_pay(self, member_id, current_paid, current_amount):
        """Handles single installment payment update for a member."""
        payload = {
            "total_paid": current_paid + 1,
            "amount": current_amount + 1000
        }
        self.update_member_db(member_id, payload)

    def handle_retract_member(self, member_id, status: bool):
        """Handles retracting or restoring member status."""
        payload = {"ret": status}
        if status and member_id in self.all_data:
            member_name = self.all_data[member_id].get("name", "مجهول")
            member_amount = self.all_data[member_id].get("amount", 0)
            self.log_notification(type_char="u", text_content=f"إنسحب {member_name} وسحب مبلغ {member_amount:,.0f} جنيه")
        self.update_member_db(member_id, payload)

    def show_edit_name_dialog(self, member_id, current_name):
        """Displays dialog for editing existing member name."""
        name_input = ft.TextField(label="تعديل اسم المشترك", value=current_name, autofocus=True)
        
        def save_name_edit(e):
            if name_input.value.strip():
                payload = {"name": name_input.value.strip()}
                self.page.dialog.open = False
                self.update_member_db(member_id, payload)

        dialog = ft.AlertDialog(
            title=ft.Text("تعديل الاسم", text_align="right", size=15),
            content=name_input,
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.TextButton("حفظ", on_click=save_name_edit)
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_multi_pay_dialog(self, member_id, current_paid, current_amount):
        """Displays dialog for handling multiple installments payment."""
        fridays_input = ft.TextField(label="عدد الجمعات", keyboard_type=ft.KeyboardType.NUMBER, text_size=10)
        
        def confirm_pay(e):
            try:
                count = int(fridays_input.value)
                if count > 0:
                    payload = {
                        "total_paid": current_paid + count,
                        "amount": current_amount + (count * 1000)
                    }
                    self.page.dialog.open = False
                    self.update_member_db(member_id, payload)
            except ValueError:
                pass

        dialog = ft.AlertDialog(
            title=ft.Text("دفع جمعات متعددة", text_align="right", size=15),
            content=fridays_input,
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.TextButton("تأكيد الدفع", on_click=confirm_pay)
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_add_member_dialog(self, e):
        """Displays dialog for inserting a new member with m=0 flag."""
        name_input = ft.TextField(label="اسم المشترك الجديد", autofocus=True)
        
        def save_new_member(ev):
            if name_input.value.strip():
                calculated_start_date = get_last_fr()
                new_member = {
                    "name": name_input.value.strip(),
                    "amount": 1000,
                    "total_paid": 0,
                    "start_date": calculated_start_date,
                    "ret": False,
                    "m": 0  # New member defaults strictly to m = 0
                }
                self.page.dialog.open = False
                self.add_new_member_db(new_member)

        dialog = ft.AlertDialog(
            title=ft.Text("إضافة مشترك جديد", text_align="right", size=15),
            content=ft.Column(controls=[name_input], tight=True, spacing=10),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: setattr(self.page.dialog, "open", False) or self.page.update()),
                ft.TextButton("حفظ المشترك", on_click=save_new_member)
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def render_data(self, data, query=""):
        """Filters data strictly by m=0 condition and updates main lists and stat widgets."""
        self.active_members_list.controls.clear()
        self.retracted_members_list.controls.clear()
        
        total, paid, pending, retracted_count, total_balance = 0, 0, 0, 0, 0
        total_withdrawals = self.get_total_amounts("w")
        total_donations = self.get_total_amounts("don")
        
        if data:
            for key, val in data.items():
                if not isinstance(val, dict): 
                    continue
                
                # Strict filter requirement: only display records where m == 0
                if val.get("m") != 0:
                    continue

                if query and query not in val.get("name", ""): 
                    continue
                
                p_icon_col = ft.colors.ORANGE_100
                
                if val.get('ret') == True:
                    retracted_count += 1
                    self.retracted_members_list.controls.append(
                        ft.ListTile(
                            leading=ft.GestureDetector(
                                content=ft.CircleAvatar(content=ft.Icon(ft.icons.PERSON_OFF, color=ft.colors.RED_600), bgcolor=ft.colors.GREY_900),
                                on_tap=lambda e, k=key, n=val.get("name", ""): self.show_edit_name_dialog(k, n)
                            ),
                            title=ft.Text(val.get("name", "مجهول"), color=ft.colors.GREY_400),
                            subtitle=ft.Text("منسحب من البرنامج", color=ft.colors.RED_400, size=13),
                            trailing=ft.IconButton(
                                icon=ft.icons.UNDO,
                                icon_color=ft.colors.GREEN_400,
                                on_click=lambda e, k=key: self.handle_retract_member(k, False),
                            )
                        )
                    )
                    continue
                
                total += 1
                total_balance += val.get("amount", 0)
                
                start_date_str = val.get("start_date", "2026-06-19")
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                except Exception:
                    start_date = START_DATE
                    
                fridays_passed = (datetime.now() - start_date).days // 7
                balance = val.get("total_paid", 0) - fridays_passed
                
                status_text = f"متأخر {abs(balance)} جمعة" if balance < 0 else ("تم الدفع" if balance == 0 else f"مقدم {balance} جمعة")
                icon_color = "#e56328" if balance < 0 else ft.colors.LIME_700
                
                if balance < 0:
                    pending += 1
                    status_button = ft.IconButton(
                        icon=ft.icons.CANCEL, 
                        icon_color=icon_color,
                        on_click=lambda e, k=key, p=val.get("total_paid", 0), a=val.get("amount", 0): self.handle_quick_pay(k, p, a),
                    )
                else:
                    paid += 1
                    status_button = ft.Icon(ft.icons.CHECK_CIRCLE, color=icon_color)
                
                subtitle_content = ft.Column(
                    controls=[
                        ft.Text(status_text, color=ft.colors.GREY_500, size=13),
                        ft.Container(height=10),
                        ft.Row(
                            controls=[
                                status_button,
                                ft.IconButton(
                                    icon=ft.icons.ADD, 
                                    icon_color=ft.colors.ORANGE_100,
                                    on_click=lambda e, k=key, p=val.get("total_paid", 0), a=val.get("amount", 0): self.show_multi_pay_dialog(k, p, a),
                                ),
                                ft.IconButton(
                                    icon=ft.icons.PERSON_REMOVE,
                                    icon_color=ft.colors.RED_400,
                                    on_click=lambda e, k=key: self.handle_retract_member(k, True),
                                )
                            ],
                            tight=True,
                            spacing=15
                        )
                    ],
                    spacing=0,
                    tight=True
                )

                title_content = ft.Column(
                    controls=[
                        ft.Text(val.get("name", "مجهول"), color=ft.colors.GREY_200),
                        ft.Container(height=8)
                    ],
                    spacing=0,
                    tight=True
                )

                self.active_members_list.controls.append(
                    ft.ListTile(
                        leading=ft.GestureDetector(
                            content=ft.CircleAvatar(content=ft.Icon(ft.icons.PERSON, color=p_icon_col), bgcolor=ft.colors.GREY_900),
                            on_tap=lambda e, k=key, n=val.get("name", ""): self.show_edit_name_dialog(k, n)
                        ),
                        title=title_content,
                        subtitle=subtitle_content,
                        is_three_line=True
                    )
                )
        
        self.tools_section.update_stats(total, paid, pending)
        display_val = f"{(total_balance - total_withdrawals):,.0f}"
        self.total_balance_text_header.value = display_val
        self.total_balance_text_body.value = f"{total_donations:,.0f}"
        self.total_retracted.value = str(retracted_count)
        self.page.update()

    def close_onboarding(self, e):
        """Closes onboarding view screen and triggers initial data loading."""
        self.page.client_storage.set("onboarding_seen", "true")
        self.onboarding_container.visible = False
        self.add_member_button.visible = True
        self.page.update()
        self.load_data()

    def route_change(self, e):
        """Handles application route navigation."""
        self.page.views.clear()
        
        if self.page.route == "/notifications":
            self.page.views.append(get_notifications_view(self.page))
        else:
            header = ft.Card(
                margin=ft.margin.all(0), 
                elevation=5, 
                content=ft.Container(
                    padding=20, 
                    border_radius=10, 
                    gradient=ft.LinearGradient(begin=ft.alignment.bottom_left, end=ft.alignment.top_right, colors=["#110111", "#111212"]), 
                    content=ft.Column(
                        spacing=10, 
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN, 
                                controls=[
                                    ft.Row([ft.Text("أموال المشتركين", size=18, color=ft.colors.ORANGE_300), self.total_balance_text_header, ft.Text("جنيه", size=18, color=ft.colors.ORANGE_400)], spacing=3), 
                                    build_notification_icon(self.page)
                                ]
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=10,
                                controls=[
                                    ft.ElevatedButton(
                                        text="سحب أموال",
                                        icon=ft.icons.REMOVE_CIRCLE_OUTLINED,
                                        style=ft.ButtonStyle(bgcolor=ft.colors.RED_900, color=ft.colors.WHITE),
                                        on_click=lambda e: self.show_finance_dialog(is_withdraw=True)
                                    ),
                                    ft.ElevatedButton(
                                        text="إيداع أموال",
                                        icon=ft.icons.ADD_CIRCLE_OUTLINED,
                                        style=ft.ButtonStyle(bgcolor=ft.colors.LIME_900, color=ft.colors.WHITE),
                                        on_click=lambda e: self.show_finance_dialog(is_withdraw=False)
                                    )
                                ]
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_EVENLY, 
                                controls=[
                                    ft.Column([ft.Text("الجمعات", size=14, color=ft.colors.GREY_300), ft.Text(str(self.total_fridays), size=16, weight="bold", color=ft.colors.GREY_300)], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                    ft.VerticalDivider(), 
                                    ft.Column([ft.Text("التبرعات", size=14, color=ft.colors.GREY_300), self.total_balance_text_body], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                    ft.VerticalDivider(), 
                                    ft.Column([ft.Text("المنسحبين", size=14, color=ft.colors.GREY_300), self.total_retracted], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                ]
                            )
                        ]
                    )
                )
            )
            
            self.page.views.append(
                ft.View(
                    "/", 
                    bgcolor=ft.colors.BLACK, 
                    padding=ft.padding.only(top=50, left=15, right=15), 
                    controls=[
                        ft.Stack(
                            expand=True, 
                            controls=[
                                ft.Column([header, self.tools_section, self.search_field, self.tabs], spacing=5), 
                                self.loading_overlay, 
                                self.onboarding_container
                            ]
                        )
                    ], 
                    floating_action_button=self.add_member_button
                )
            )
        self.page.update()

    def start(self):
        """Initializes application startup sequence."""
        self.setup_page()
        if not self.page.client_storage.get("onboarding_seen"): 
            self.onboarding_container.visible = True
        else: 
            self.add_member_button.visible = True
            self.load_data()
        self.page.go("/")


class ToolsComponent(ft.Container):
    """Component encapsulation for tools statistical indicators."""
    def __init__(self):
        super().__init__()
        self.total_members = ft.Text("0", color=ft.colors.GREY_300, size=24, weight="bold")
        self.paid_members = ft.Text("0", color=ft.colors.LIME_700, size=24, weight="bold")
        self.pending_members = ft.Text("0", color="#e56328", size=24, weight="bold")
        self.content = ft.Row(
            spacing=5, 
            controls=[
                self.tool_item("المشتركين", self.total_members), 
                self.tool_item("المسددين", self.paid_members), 
                self.tool_item("المطالبين", self.pending_members)
            ]
        )
        
    def tool_item(self, title, counter):
        """Generates statistical display item layout container."""
        color = ft.colors.GREY_300 if title == "المشتركين" else (ft.colors.LIME_700 if title == "المسددين" else "#e56328")
        return ft.Container(
            expand=True, 
            height=80, 
            bgcolor=ft.colors.GREY_900, 
            border_radius=5, 
            padding=10, 
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER, 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                controls=[ft.Text(title, color=color, size=12), counter]
            ),
            gradient=ft.LinearGradient(begin=ft.alignment.bottom_center, end=ft.alignment.top_center, colors=["#111113", "#111112"])
        )
        
    def update_stats(self, total, paid, pending):
        """Updates text counters for total, paid and pending members."""
        self.total_members.value = str(total)
        self.paid_members.value = str(paid)
        self.pending_members.value = str(pending)


def main(page: ft.Page):
    app = SubscriptionApp(page)
    app.start()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=1111)
