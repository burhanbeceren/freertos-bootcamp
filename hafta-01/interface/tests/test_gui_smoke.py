"""GUI'nin açılabildiğini doğrular (ekransız)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_builds():
    from PySide6.QtWidgets import QApplication
    from uart_monitor.gui import MainWindow

    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.session.feed_line("ACK,SCN,S3")
    w.session.feed_line("ACK,START,S3")
    w.session.feed_line("ACK,STOP,S3")
    w.session.feed_line("LOG,S3,1,10,20,30,40,5640,ok")
    w.session.feed_line("LOG,S3,2,10,20,30,,,tx_drop")
    w.session.feed_line("END,DUMP,S3")
    w._show_results()
    assert w.stats_tbl.rowCount() > 10
    w.close()


def test_analysis_tabs_build(tmp_path):
    from PySide6.QtWidgets import QApplication
    from uart_monitor.analysis_view import AnalysisView, MeasurementsView

    app = QApplication.instance() or QApplication([])
    mv = MeasurementsView(lambda: tmp_path)      # boş klasör: çökmemeli
    mv.refresh()
    av = AnalysisView(lambda: tmp_path)
    av.run()
    assert "bulunamadı" in av.status.text()
