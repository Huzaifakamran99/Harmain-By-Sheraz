from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QCheckBox, QPushButton, QTabWidget, QMessageBox, QFileDialog, QFrame,
    QColorDialog,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QColor

from presentation.app_context import AppContext, handle_error
from presentation.themes import THEME_NAMES
from presentation.widgets.inputs import StyledComboBox
from core.exceptions import ApplicationError
from core.config import get_branding_dir, get_logo_path, LOGO_FILENAMES, DEFAULT_UPCOMING_COLOR


class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str)
    password_change_requested = pyqtSignal()
    branding_changed = pyqtSignal()
    scheduler_interval_changed = pyqtSignal(int)
    email_settings_saved = pyqtSignal()

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)   # never cut a tab title
        tabs.tabBar().setUsesScrollButtons(True)

        # --- General ---
        general_tab = QWidget()
        general_form = QFormLayout(general_tab)
        self.theme_combo = StyledComboBox()
        self.theme_combo.addItems(THEME_NAMES)
        self.theme_combo.currentTextChanged.connect(self._apply_theme)
        reset_theme_btn = QPushButton("Reset to Default")
        reset_theme_btn.setObjectName("SecondaryButton")
        reset_theme_btn.clicked.connect(self._reset_theme)
        theme_row = QHBoxLayout()
        theme_row.addWidget(self.theme_combo)
        theme_row.addWidget(reset_theme_btn)
        self.default_charge_input = QSpinBox()
        self.default_charge_input.setRange(0, 1_000_000)
        self.contact_number_input = QLineEdit()
        self.contact_number_input.setPlaceholderText("e.g. +92 300 1234567")
        self.reminder_days_input = QSpinBox()
        self.reminder_days_input.setRange(0, 30)
        self.transfer_hours_input = QSpinBox()
        self.transfer_hours_input.setRange(1, 72)
        self.scheduler_interval_input = QSpinBox()
        self.scheduler_interval_input.setRange(1, 120)
        # --- highlight colour for permits inside the reminder window
        self._upcoming_color = DEFAULT_UPCOMING_COLOR
        self.upcoming_preview = QLabel("Sample Pilgrim - permit soon")
        self.upcoming_preview.setMinimumWidth(0)
        choose_color_btn = QPushButton("Choose Colour")
        choose_color_btn.setObjectName("SecondaryButton")
        choose_color_btn.setMinimumWidth(150)
        choose_color_btn.setToolTip("Pick the colour used for pilgrims whose permit is coming up")
        choose_color_btn.clicked.connect(self._pick_upcoming_color)
        reset_color_btn = QPushButton("Reset to Red")
        reset_color_btn.setObjectName("SecondaryButton")
        reset_color_btn.setMinimumWidth(150)
        reset_color_btn.clicked.connect(lambda: self._set_upcoming_color(DEFAULT_UPCOMING_COLOR))
        color_row = QHBoxLayout()
        color_row.addWidget(self.upcoming_preview, 1)
        color_row.addWidget(choose_color_btn)
        color_row.addWidget(reset_color_btn)
        self._set_upcoming_color(DEFAULT_UPCOMING_COLOR)

        general_form.addRow("Theme", theme_row)
        general_form.addRow("Default Charge (PKR)", self.default_charge_input)
        general_form.addRow("Your Contact Number (shown on reminder emails)", self.contact_number_input)
        general_form.addRow("Reminder Window (days before permit)", self.reminder_days_input)
        general_form.addRow("Upcoming Permit Colour", color_row)
        general_form.addRow("Auto-transfer After (hours)", self.transfer_hours_input)
        general_form.addRow("Background Check Interval (minutes)", self.scheduler_interval_input)
        general_save = QPushButton("Save General Settings")
        general_save.clicked.connect(self._save_general)
        general_form.addRow(general_save)
        tabs.addTab(general_tab, "General")

        # --- Email ---
        email_tab = QWidget()
        email_form = QFormLayout(email_tab)
        self.smtp_host_input = QLineEdit()
        self.smtp_port_input = QSpinBox()
        self.smtp_port_input.setRange(1, 65535)
        self.smtp_username_input = QLineEdit()
        self.smtp_password_input = QLineEdit()
        self.smtp_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_sender_input = QLineEdit()
        self.reminder_recipient_input = QLineEdit()
        self.reminder_recipient_input.setPlaceholderText("your own email - reminders are sent here only")
        self.smtp_tls_checkbox = QCheckBox("Use TLS")
        self.reminder_logo_checkbox = QCheckBox("Include my logo in reminder emails")
        email_form.addRow("SMTP Host", self.smtp_host_input)
        email_form.addRow("SMTP Port", self.smtp_port_input)
        email_form.addRow("SMTP Username", self.smtp_username_input)
        email_form.addRow("SMTP Password", self.smtp_password_input)
        email_form.addRow("Sender Email Address", self.smtp_sender_input)
        email_form.addRow("Send Reminders To (you)", self.reminder_recipient_input)
        email_form.addRow(self.smtp_tls_checkbox)
        email_form.addRow(self.reminder_logo_checkbox)
        email_save = QPushButton("Save Email Settings")
        email_save.clicked.connect(self._save_email)
        email_form.addRow(email_save)
        tabs.addTab(email_tab, "Email")

        # --- WhatsApp ---
        whatsapp_tab = QWidget()
        whatsapp_form = QFormLayout(whatsapp_tab)
        note = QLabel(
            "Connect an authorized WhatsApp Business provider (e.g. Meta Cloud API, Twilio, 360dialog).\n"
            "Unauthorized automation or scraping of personal WhatsApp is not supported here."
        )
        note.setWordWrap(True)
        note.setObjectName("BrandSubLabel")
        whatsapp_form.addRow(note)
        self.whatsapp_url_input = QLineEdit()
        self.whatsapp_token_input = QLineEdit()
        self.whatsapp_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.whatsapp_sender_input = QLineEdit()
        whatsapp_form.addRow("Provider API URL", self.whatsapp_url_input)
        whatsapp_form.addRow("API Token", self.whatsapp_token_input)
        whatsapp_form.addRow("Sender ID", self.whatsapp_sender_input)
        whatsapp_save = QPushButton("Save WhatsApp Settings")
        whatsapp_save.clicked.connect(self._save_whatsapp)
        whatsapp_form.addRow(whatsapp_save)
        tabs.addTab(whatsapp_tab, "WhatsApp")

        # --- Account ---
        account_tab = QWidget()
        account_layout = QVBoxLayout(account_tab)
        change_pw_btn = QPushButton("Change My Password")
        change_pw_btn.clicked.connect(self.password_change_requested.emit)
        account_layout.addWidget(change_pw_btn)
        account_layout.addStretch()
        tabs.addTab(self._build_branding_tab(), "Branding && Bill")
        tabs.addTab(self._build_reading_tab(), "Document Reading")
        tabs.addTab(account_tab, "Account")

        layout.addWidget(tabs)

    def _load_settings(self):
        s = self.ctx.settings.get_all()
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(s.get("theme", "Dark Gold"))
        self.theme_combo.blockSignals(False)
        self.default_charge_input.setValue(int(float(s.get("default_charge", 200))))
        self.contact_number_input.setText(s.get("business_contact_number", ""))
        self.reminder_days_input.setValue(int(s.get("reminder_days", 2)))
        self._set_upcoming_color(self.ctx.settings.upcoming_color())
        self.transfer_hours_input.setValue(int(s.get("transfer_hours", 6)))
        self.scheduler_interval_input.setValue(int(s.get("scheduler_interval_minutes", 5)))
        self.smtp_host_input.setText(s.get("smtp_host", ""))
        self.smtp_port_input.setValue(int(s.get("smtp_port", 587) or 587))
        self.smtp_username_input.setText(s.get("smtp_username", ""))
        self.smtp_password_input.setText(s.get("smtp_password", ""))
        self.smtp_sender_input.setText(s.get("smtp_sender", ""))
        self.reminder_recipient_input.setText(s.get("reminder_recipient", ""))
        self.smtp_tls_checkbox.setChecked(s.get("smtp_use_tls", "1") == "1")
        self.reminder_logo_checkbox.setChecked(s.get("reminder_email_logo", "0") == "1")
        self.whatsapp_url_input.setText(s.get("whatsapp_api_url", ""))
        self.whatsapp_token_input.setText(s.get("whatsapp_api_token", ""))
        self.whatsapp_sender_input.setText(s.get("whatsapp_sender_id", ""))
        self.business_name_input.setText(s.get("business_name", ""))
        self.bill_subtitle_input.setText(s.get("bill_subtitle", ""))
        self.bill_footer_input.setText(s.get("bill_footer_text", ""))
        self._refresh_logo_preview()

    def _apply_theme(self, theme_name: str):
        self.theme_changed.emit(theme_name)
        try:
            self.ctx.settings.set("theme", theme_name, actor=self.ctx.current_username)
        except Exception as e:
            handle_error(self, e, "Settings")

    def _reset_theme(self):
        from core.config import DEFAULT_THEME_NAME
        self.theme_combo.setCurrentText(DEFAULT_THEME_NAME)

    def _set_upcoming_color(self, colour: str):
        self._upcoming_color = colour
        self.upcoming_preview.setStyleSheet(
            f"color: {colour}; font-weight: 700; padding: 6px 10px 6px 10px;"
            f"border-left: 8px solid {colour}; background: transparent;"
        )

    def _pick_upcoming_color(self):
        chosen = QColorDialog.getColor(QColor(self._upcoming_color), self, "Choose highlight colour")
        if chosen.isValid():
            self._set_upcoming_color(chosen.name())      # '#rrggbb'

    def _save_general(self):
        try:
            self.ctx.settings.set_many({
                "default_charge": self.default_charge_input.value(),
                "business_contact_number": self.contact_number_input.text().strip(),
                "reminder_days": self.reminder_days_input.value(),
                "upcoming_color": self._upcoming_color,
                "transfer_hours": self.transfer_hours_input.value(),
                "scheduler_interval_minutes": self.scheduler_interval_input.value(),
            }, actor=self.ctx.current_username)
            self.scheduler_interval_changed.emit(self.scheduler_interval_input.value())
            QMessageBox.information(self, "Settings", "General settings saved.")
        except ApplicationError as e:
            QMessageBox.warning(self, "Settings", e.user_message)
        except Exception as e:
            handle_error(self, e, "Settings")

    def _save_email(self):
        try:
            from domain.rules import check_email
            level, message = check_email(self.reminder_recipient_input.text().strip())
            if level == "error":
                QMessageBox.warning(self, "Send Reminders To", message)
                return
            self.ctx.settings.set_many({
                "reminder_recipient": self.reminder_recipient_input.text().strip(),
                "reminder_email_logo": "1" if self.reminder_logo_checkbox.isChecked() else "0",
                "smtp_host": self.smtp_host_input.text().strip(),
                "smtp_port": self.smtp_port_input.value(),
                "smtp_username": self.smtp_username_input.text().strip(),
                "smtp_password": self.smtp_password_input.text(),
                "smtp_sender": self.smtp_sender_input.text().strip(),
                "smtp_use_tls": "1" if self.smtp_tls_checkbox.isChecked() else "0",
            }, actor=self.ctx.current_username)
            self.email_settings_saved.emit()
            QMessageBox.information(self, "Settings", "Email settings saved.")
        except Exception as e:
            handle_error(self, e, "Settings")

    def _save_whatsapp(self):
        try:
            self.ctx.settings.set_many({
                "whatsapp_api_url": self.whatsapp_url_input.text().strip(),
                "whatsapp_api_token": self.whatsapp_token_input.text().strip(),
                "whatsapp_sender_id": self.whatsapp_sender_input.text().strip(),
            }, actor=self.ctx.current_username)
            QMessageBox.information(self, "Settings", "WhatsApp settings saved.")
        except Exception as e:
            handle_error(self, e, "Settings")

    # ------------------------------------------------------ Branding & Bill
    def _build_branding_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        intro = QLabel(
            "These details appear in the sidebar of the app and in the header and "
            "footer of every A6 permit slip."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(10)
        self.business_name_input = QLineEdit()
        self.business_name_input.setPlaceholderText("e.g. HaramaIn by Sheraz")
        self.bill_subtitle_input = QLineEdit()
        self.bill_subtitle_input.setPlaceholderText("e.g. Riyazul Jannah Permit Slip")
        self.bill_footer_input = QLineEdit()
        self.bill_footer_input.setPlaceholderText("e.g. Thank you for choosing HaramaIn")
        form.addRow("Business Name", self.business_name_input)
        form.addRow("Bill Subtitle", self.bill_subtitle_input)
        form.addRow("Bill Footer Line", self.bill_footer_input)
        layout.addLayout(form)

        logo_panel = QFrame()
        logo_panel.setObjectName("GlassPanel")
        logo_layout = QVBoxLayout(logo_panel)
        logo_layout.setContentsMargins(16, 14, 16, 14)
        logo_layout.setSpacing(10)

        logo_heading = QLabel("LOGO")
        logo_heading.setObjectName("CardTitle")
        logo_layout.addWidget(logo_heading)

        self.logo_preview = QLabel()
        self.logo_preview.setMinimumHeight(84)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        logo_layout.addWidget(self.logo_preview)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        import_btn = QPushButton("Import Logo...")
        import_btn.setMinimumWidth(160)
        import_btn.clicked.connect(self._import_logo)
        remove_btn = QPushButton("Remove Logo")
        remove_btn.setObjectName("SecondaryButton")
        remove_btn.setMinimumWidth(140)
        remove_btn.clicked.connect(self._remove_logo)
        logo_row.addWidget(import_btn)
        logo_row.addWidget(remove_btn)
        logo_row.addStretch()
        logo_layout.addLayout(logo_row)

        hint = QLabel(
            "A square or wide PNG with a transparent background works best. "
            "The logo is copied into the app's own folder, so it keeps working "
            "even if you move or delete the original file."
        )
        hint.setObjectName("HintText")
        hint.setWordWrap(True)
        logo_layout.addWidget(hint)
        layout.addWidget(logo_panel)

        save_btn = QPushButton("Save Branding")
        save_btn.setMinimumWidth(180)
        save_btn.clicked.connect(self._save_branding)
        layout.addWidget(save_btn)
        layout.addStretch()
        return tab

    def _refresh_logo_preview(self):
        logo = get_logo_path()
        if not logo:
            self.logo_preview.setPixmap(QPixmap())
            self.logo_preview.setText("No logo imported yet.")
            return
        pixmap = QPixmap(str(logo))
        if pixmap.isNull():
            self.logo_preview.setText("The imported file could not be displayed.")
            return
        self.logo_preview.setText("")
        self.logo_preview.setPixmap(pixmap.scaled(
            240, 80, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def _import_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.ico);;All files (*)",
        )
        if not file_path:
            return
        source = Path(file_path)
        suffix = source.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".ico"}:
            QMessageBox.warning(self, "Logo", "Please choose a PNG, JPG, WEBP, BMP or ICO image.")
            return
        try:
            folder = get_branding_dir()
            for name in LOGO_FILENAMES:          # only one logo at a time
                existing = folder / name
                if existing.exists():
                    existing.unlink()
            shutil.copy2(source, folder / f"logo{suffix}")
        except OSError as e:
            QMessageBox.warning(self, "Logo", f"The logo could not be imported: {e}")
            return
        self._refresh_logo_preview()
        self.branding_changed.emit()
        QMessageBox.information(
            self, "Logo",
            "Logo imported. It now appears in the sidebar and on every new bill.",
        )

    def _remove_logo(self):
        folder = get_branding_dir()
        removed = False
        for name in LOGO_FILENAMES:
            candidate = folder / name
            if candidate.exists():
                try:
                    candidate.unlink()
                    removed = True
                except OSError:
                    pass
        self._refresh_logo_preview()
        self.branding_changed.emit()
        if not removed:
            QMessageBox.information(self, "Logo", "There was no imported logo to remove.")

    def _save_branding(self):
        try:
            self.ctx.settings.set_many({
                "business_name": self.business_name_input.text().strip(),
                "bill_subtitle": self.bill_subtitle_input.text().strip(),
                "bill_footer_text": self.bill_footer_input.text().strip(),
            }, actor=self.ctx.current_username)
            self.branding_changed.emit()
            QMessageBox.information(self, "Settings", "Branding saved.")
        except Exception as e:
            handle_error(self, e, "Settings")

    # ---------------------------------------------------- Document Reading
    def _build_reading_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        intro = QLabel(
            "When you upload a passport or visa, the app tries several ways of reading "
            "it and stops at the first that works. This page shows which of them are "
            "available on this computer."
        )
        intro.setObjectName("PageSubtitle")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.reading_panel = QFrame()
        self.reading_panel.setObjectName("GlassPanel")
        self.reading_layout = QVBoxLayout(self.reading_panel)
        self.reading_layout.setContentsMargins(16, 14, 16, 14)
        self.reading_layout.setSpacing(8)
        layout.addWidget(self.reading_panel)

        recheck_btn = QPushButton("Check Again")
        recheck_btn.setObjectName("SecondaryButton")
        recheck_btn.setMinimumWidth(150)
        recheck_btn.clicked.connect(self._refresh_reading_panel)
        layout.addWidget(recheck_btn)
        layout.addStretch()

        self._refresh_reading_panel()
        return tab

    def _refresh_reading_panel(self):
        while self.reading_layout.count():
            item = self.reading_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        caps = self.ctx.documents.reading_capabilities()
        rows = [
            ("Digital PDF visas (text layer)", caps["can_read_digital_pdf"],
             "Needs pdfplumber, PyMuPDF or pypdf - all installed by pip."),
            ("Scanned PDF documents", caps["can_read_scanned_pdf"],
             "Needs PyMuPDF (pip install PyMuPDF) plus Tesseract OCR."),
            ("Photos and image scans", caps["can_read_images"],
             "Needs the Tesseract OCR program installed on this computer."),
        ]
        for label, ok, note in rows:
            row = QLabel(f"{'✔' if ok else '✖'}   {label}")
            row.setObjectName("SuccessText" if ok else "ErrorText")
            self.reading_layout.addWidget(row)
            detail = QLabel(f"      {note}")
            detail.setObjectName("HintText")
            detail.setWordWrap(True)
            self.reading_layout.addWidget(detail)

        problems = self.ctx.documents.reading_problems()
        for name, reason in problems.items():
            detail = QLabel(f"      {name}: {reason}")
            detail.setObjectName("HintText")
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.reading_layout.addWidget(detail)
        where = QLabel(f"      This app is running with Python at: {sys.executable}")
        where.setObjectName("HintText")
        where.setWordWrap(True)
        where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reading_layout.addWidget(where)

        hint = self.ctx.documents.setup_hint()
        if hint:
            warning = QLabel(hint)
            warning.setObjectName("ErrorText")
            warning.setWordWrap(True)
            self.reading_layout.addWidget(warning)
        else:
            done = QLabel("Everything needed for automatic reading is installed.")
            done.setObjectName("SuccessText")
            done.setWordWrap(True)
            self.reading_layout.addWidget(done)
