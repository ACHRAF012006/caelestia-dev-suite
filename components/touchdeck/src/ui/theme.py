def stylesheet(theme, accent):
    bg, card, text, edge = {
        "Dark": ("#12151b", "#20242d", "#e1e5ed", "#353b47"),
        "OLED Dark": ("#000000", "#0d1015", "#e1e5ed", "#292f39"),
        "Light": ("#eef0f4", "#ffffff", "#202630", "#c8ced9")
    }[theme]
    return f"""
    QWidget {{ background: {bg}; color: {text}; font-family: sans-serif; font-size: 14px; }}
    QFrame#tile {{ background: {card}; border: 1px solid {edge}; border-radius: 18px; }}
    QFrame#tile QLabel {{ background: transparent; border: none; }}
    QPushButton, QToolButton {{ background: {card}; border: 1px solid {edge}; border-radius: 12px; padding: 9px; min-height: 28px; }}
    QPushButton:pressed {{ background: {accent}; color: #11151b; }}
    QPushButton:checked {{ border: 2px solid {accent}; }}
    QPushButton:disabled {{ color: #727986; }}
    QComboBox, QLineEdit, QSpinBox {{ background: {card}; border: 1px solid {edge}; border-radius: 10px; padding: 8px; min-height: 30px; }}
    QComboBox::drop-down {{ width: 36px; }}
    QComboBox QAbstractItemView {{ selection-background-color: {accent}; min-height: 48px; }}
    QListWidget, QPlainTextEdit {{ background: {card}; border: 1px solid {edge}; border-radius: 10px; }}
    QListWidget::item {{ padding: 12px; min-height: 28px; }}
    QCheckBox {{ spacing: 12px; min-height: 48px; }}
    QCheckBox::indicator {{ width: 28px; height: 28px; }}
    QSlider::groove:horizontal {{ height: 10px; background: {edge}; border-radius: 5px; }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 5px; }}
    QSlider::handle:horizontal {{ width: 30px; margin: -10px 0; border-radius: 15px; background: {text}; }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ width: 14px; background: {bg}; }}
    QScrollBar::handle:vertical {{ background: {edge}; min-height: 40px; border-radius: 7px; }}
    QTabBar::tab {{ padding: 12px; min-height: 28px; }}
    QMenu::item {{ padding: 14px 24px; }}
    QLabel#toast {{ background: {card}; border: 1px solid {accent}; border-radius: 12px; padding: 12px; }}
    """
