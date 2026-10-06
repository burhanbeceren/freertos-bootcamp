"""GUI'nin açılabildiğini doğrular (ekransız). Satırlar BİÇİM ÖRNEĞİDİR, ölçüm değildir."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_main_window_live_flow(tmp_path):
    from uart_monitor.gui import MainWindow

    app = _app()
    w = MainWindow()
    w.out_dir = tmp_path
    w.autosave_cb.setChecked(False)
    for ln in ["ACK,SCN,S3", "ACK,START,S3,C,INJ,2", "TEL,1,S3,100,0,0,0,420,2930",
               "TEL,2,S3,10100,0,0,1,421,2930", "BTN,1,S3,PRESSED,200,207",
               "ACK,STOP,S3", "LOG,S3,1,200,207,215,230,5780,ok", "LOG,S3,2,900,907,915,,,tx_drop",
               "INF,variant,C", "INF,source,INJ", "END,DUMP,S3"]:
        w.pending.append(("t", ln))
    w._flush()
    app.processEvents()
    assert w.session.variant == "C" and w.session.source == "INJ"
    assert w.stats["n"].text() == "1 / 2"
    assert w.stats["met"].text() == "%50"
    assert w.events.rowCount() == 2
    assert w.session.tel_period_us() == 10000
    paths = w.session.save(tmp_path)
    assert paths[0] == tmp_path / "runs" / "C-INJ" / "S3.csv"
    w._refresh_sessions()
    assert w.sess_cb.count() == 2
    w.close()


def test_analysis_tabs_build(tmp_path):
    from uart_monitor.analysis_view import AnalysisView, MeasurementsView

    _app()
    mv = MeasurementsView(lambda: tmp_path)      # boş klasör: çökmemeli
    mv.refresh()
    av = AnalysisView(lambda: tmp_path)
    av.run()
    assert "bulunamadı" in av.status.text()
