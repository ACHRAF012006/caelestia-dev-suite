from PySide6.QtWidgets import QApplication, QWidget
from app.review import ReviewDialog


def test_readable_summary_hides_exact_plan_until_requested():
    app = QApplication.instance() or QApplication([])
    parent = QWidget(); parent.resize(1000, 800)
    options = QWidget(); options.plan = {"reviewed": True}
    options.summary_text = "Install an independent app. Existing versions are backed up."
    exact = "WRITE /temporary/owned/path\nCOMPLETE COMPONENT SOURCE\nprint('source')"
    review = ReviewDialog(parent, "Install Example", exact, "Install", options)
    review.show(); app.processEvents()
    assert review.summary.toPlainText() == options.summary_text
    assert review.details.isHidden() and review.accept_button.isEnabled()
    review.details_toggle.click(); assert not review.details.isHidden()
    assert review.details.toPlainText() == exact
    options.summary_text = "An unrelated desktop file already exists. Choose another filename."
    options.refresh_preview("Exact collision details", False)
    assert not review.accept_button.isEnabled()
    assert review.summary.toPlainText() == options.summary_text
    options.summary_text = "Safe alternate filename selected."
    options.refresh_preview("WRITE /temporary/alternate.desktop", True)
    assert review.accept_button.isEnabled()
    assert review.details.toPlainText().endswith("alternate.desktop")
    review.close(); parent.close(); app.processEvents()


def test_invalid_initial_plan_cannot_be_accepted():
    app = QApplication.instance() or QApplication([])
    parent = QWidget(); options = QWidget(); options.plan = None
    options.summary_text = "Cannot overwrite an unrelated file."
    review = ReviewDialog(parent, "Install", "Conflict details", "Install", options)
    assert not review.accept_button.isEnabled()
    review.close(); parent.close(); app.processEvents()
