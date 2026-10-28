import math

from PyQt5.QtCore import (Qt, QPointF, QRectF, QPropertyAnimation, QTimer,
                          pyqtSignal)
from PyQt5.QtGui import (QPainter, QPainterPath, QColor, QFont, QPen, QBrush,
                         QLinearGradient)
from PyQt5.QtWidgets import QWidget, QLineEdit


def _polar(cx, cy, radius, angle_deg):
    rad = math.radians(angle_deg)
    return QPointF(cx + radius * math.cos(rad), cy - radius * math.sin(rad))


class PieMenu(QWidget):
    itemActivated = pyqtSignal(dict)
    searchChanged = pyqtSignal(str)
    addFavoriteRequested = pyqtSignal()
    removeFavoriteRequested = pyqtSignal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.sectors = []
        self.selected = 0
        self.hovered = -1
        self.hovered_child = -1
        self.open_child_index = -1
        self.edit_mode = False
        self._closing = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.finished.connect(self._after_close)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._open_hovered)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Digite para buscar...")
        self.search_edit.textChanged.connect(self.searchChanged.emit)
        self.search_edit.returnPressed.connect(self._activate_current)
        self.search_edit.setStyleSheet(
            "QLineEdit { background-color: rgba(10,12,16,200); color: #ffffff;"
            " border: 2px solid #00d4ff; border-radius: 18px; padding: 0 14px;"
            " font: 11pt 'Segoe UI'; selection-background-color: #2563eb; }"
            "QLineEdit:focus { border-color: #7c3aed; }"
        )
        self.search_edit.hide()

        self._apply_geometry()

    def _apply_geometry(self):
        pad = 26
        self.r_in = self.cfg["radius_inner"]
        self.r_out = self.cfg["radius_outer"]
        self.sr_in = self.cfg["subradius_inner"]
        self.sr_out = self.cfg["subradius_outer"]
        side = 2 * self.sr_out + 2 * pad + 1
        self.setFixedSize(side, side)
        self._cx = side / 2.0
        self._cy = side / 2.0

    def _c(self, key):
        return self.cfg["colors"].get(key)

    def _qc(self, key, alpha=None):
        color = QColor(self._c(key))
        if alpha is not None:
            color.setAlpha(alpha)
        return color

    def set_sectors(self, sectors):
        self.sectors = sectors
        self.selected = 0
        self.hovered = -1
        self.hovered_child = -1
        self.open_child_index = -1
        self._refresh_search_state()
        self.update()

    def show_at(self, pos):
        self._closing = False
        self.move(pos.x() - self.width() // 2, pos.y() - self.height() // 2)
        self.selected = 0
        self.hovered = -1
        self.hovered_child = -1
        self.open_child_index = -1
        self._refresh_search_state()
        self._fade.stop()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade.setDuration(self.cfg["fade_in_ms"])
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(self.cfg["alpha"])
        self._fade.start()

    def close_menu(self):
        if self._closing:
            return
        self._closing = True
        self._fade.stop()
        self._hover_timer.stop()
        self._fade_out.stop()
        self._fade_out.setDuration(self.cfg["fade_out_ms"])
        self._fade_out.setStartValue(self.windowOpacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.start()

    def _after_close(self):
        self.hide()
        self._closing = False

    def set_search_results(self, results):
        for sector in self.sectors:
            if sector.get("search"):
                sector["children"] = results
                break
        items = self.current_items()
        if items and self.selected >= len(items):
            self.selected = len(items) - 1
        self.update()

    def refresh(self):
        self.update()

    def current_items(self):
        if self.open_child_index >= 0 and self.open_child_index < len(self.sectors):
            return self.sectors[self.open_child_index].get("children") or []
        return self.sectors

    def _search_mode(self):
        if self.open_child_index < 0 or self.open_child_index >= len(self.sectors):
            return False
        return bool(self.sectors[self.open_child_index].get("search"))

    def _refresh_search_state(self):
        if self._search_mode():
            self.search_edit.show()
            self.search_edit.setFocus(Qt.OtherFocusReason)
            self.search_edit.setGeometry(
                int(self.width() / 2 - 95), int(self.height() / 2 - 20), 190, 40)
            self.searchChanged.emit(self.search_edit.text())
        else:
            self.search_edit.hide()

    def _center_title(self):
        if self._search_mode():
            text = self.search_edit.text()
            return text if text else "Busca"
        if self.edit_mode:
            return "MODO EDICAO"
        items = self.current_items()
        if items and 0 <= self.selected < len(items):
            name = items[self.selected].get("name", "")
            if len(name) > 14:
                name = name[:13] + "..."
            return name
        return "MeuLauncher"

    def _sector_path(self, r_in, r_out, start, sweep):
        rect_in = QRectF(-r_in, -r_in, 2 * r_in, 2 * r_in)
        rect_out = QRectF(-r_out, -r_out, 2 * r_out, 2 * r_out)
        a0 = start
        a1 = start + sweep
        p0 = _polar(0, 0, r_in, a0)
        path = QPainterPath()
        path.moveTo(p0)
        path.arcTo(rect_in, a0, sweep)
        path.arcTo(rect_out, a1, -sweep)
        path.closeSubpath()
        return path

    def _draw_ring(self, painter, items, r_in, r_out, start, sweep, sel_idx):
        if not items or sweep <= 0:
            return
        count = len(items)
        step = sweep / count
        text_alpha = self._c("cor_texto_alpha")
        for i, item in enumerate(items):
            a0 = start + i * step
            path = self._sector_path(r_in, r_out, a0, step)
            mid = _polar(0, 0, (r_in + r_out) / 2.0, a0 + step / 2.0)
            active = (i == sel_idx)
            if active:
                inner = _polar(0, 0, r_in, a0 + step / 2.0)
                outer = _polar(0, 0, r_out, a0 + step / 2.0)
                grad = QLinearGradient(inner, outer)
                c1 = QColor(self._c("cor_hover_inicio"))
                c1.setAlpha(self._c("cor_hover_alpha"))
                c2 = QColor(self._c("cor_hover_fim"))
                c2.setAlpha(self._c("cor_hover_alpha"))
                grad.setColorAt(0, c1)
                grad.setColorAt(1, c2)
                painter.setBrush(QBrush(grad))
                painter.setPen(QPen(self._qc("cor_glow", 170),
                                    self._c("espessura_borda") + 0.5))
                painter.drawPath(path)
                painter.setPen(QPen(self._qc("cor_glow", 70), 9))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)
            else:
                col = QColor(self._c("cor_setor_inativo"))
                col.setAlpha(self._c("cor_setor_inativo_alpha"))
                painter.setBrush(col)
                painter.setPen(QPen(self._qc("cor_borda", 150),
                                    self._c("espessura_borda")))
                painter.drawPath(path)
            icon = item.get("icon")
            pix = icon.pixmap(26, 26) if icon is not None else None
            if pix is not None and not pix.isNull():
                painter.drawPixmap(int(mid.x()) - 13, int(mid.y()) - 32, pix)
            else:
                f = QFont("Segoe UI", 10)
                f.setBold(True)
                painter.setFont(f)
                painter.setPen(self._qc("cor_texto", 220))
                painter.drawText(QRectF(mid.x() - 13, mid.y() - 34, 26, 26),
                                 Qt.AlignCenter, (item.get("name") or "?")[:1].upper())
            f2 = QFont("Segoe UI", 9)
            painter.setFont(f2)
            painter.setPen(self._qc("cor_texto", text_alpha))
            name = item.get("name", "")
            if len(name) > 12:
                name = name[:11] + "..."
            painter.drawText(QRectF(mid.x() - 70, mid.y() - 2, 140, 30),
                             Qt.AlignHCenter | Qt.AlignTop, name)

    def _draw_center(self, painter):
        r = self.r_in - 4
        col = QColor(self._c("cor_fundo"))
        col.setAlpha(self._c("fundo_alpha"))
        painter.setPen(QPen(self._qc("cor_borda", 200), 2))
        painter.setBrush(col)
        painter.drawEllipse(QPointF(0, 0), r, r)
        f = QFont("Segoe UI", 12)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(self._qc("cor_texto", 255))
        painter.drawText(QRectF(-r, -r, 2 * r, 2 * r), Qt.AlignCenter,
                         self._center_title())

    def _draw_sel_dot(self, painter, step):
        if not self.sectors:
            return
        count = len(self.sectors)
        if self.open_child_index >= 0:
            parent = self.sectors[self.open_child_index]
            children = parent.get("children") or []
            if not children:
                return
            if self.selected < 0 or self.selected >= len(children):
                return
            cstep = step / len(children)
            a0 = -90.0 + self.open_child_index * step + self.selected * cstep
            pos = _polar(0, 0, self.sr_out + 7, a0 + cstep / 2.0)
        else:
            if self.selected < 0 or self.selected >= count:
                return
            a0 = -90.0 + self.selected * step
            pos = _polar(0, 0, self.r_out + 7, a0 + step / 2.0)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(pos, 4, 4)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self._cx, self._cy)
        count = len(self.sectors)
        step = 360.0 / count if count else 0
        sel0 = self.selected if self.open_child_index < 0 else -1
        self._draw_ring(painter, self.sectors, self.r_in, self.r_out, -90.0,
                        step * count, sel0)
        if self.open_child_index >= 0 and self.open_child_index < count:
            parent = self.sectors[self.open_child_index]
            children = parent.get("children") or []
            if children:
                a0 = -90.0 + self.open_child_index * step
                self._draw_ring(painter, children, self.sr_in, self.sr_out, a0,
                                step, self.selected)
        self._draw_center(painter)
        self._draw_sel_dot(painter, step)
        painter.end()

    def _sector_at(self, x, y):
        dx = x - self._cx
        dy = y - self._cy
        dist = math.hypot(dx, dy)
        count = len(self.sectors)
        if count == 0:
            return -1, -1
        angle = math.degrees(math.atan2(-dy, dx)) % 360.0
        step = 360.0 / count
        idx = int(((angle + 90.0) % 360.0) / step)
        if idx >= count:
            idx = count - 1
        if self.open_child_index >= 0:
            parent = self.sectors[self.open_child_index]
            children = parent.get("children") or []
            if children and self.sr_in <= dist <= self.sr_out:
                p0 = -90.0 + self.open_child_index * step
                rel = (angle - p0) % 360.0
                cstep = step / len(children)
                cidx = int(rel / cstep)
                if cidx >= len(children):
                    cidx = len(children) - 1
                return idx, cidx
        if self.r_in <= dist <= self.r_out:
            return idx, -1
        return idx, -2

    def mouseMoveEvent(self, event):
        idx, cidx = self._sector_at(event.pos().x(), event.pos().y())
        count = len(self.sectors)
        if idx < 0 or count == 0:
            self.hovered = -1
            self.hovered_child = -1
            return
        if cidx == -2:
            return
        self.hovered = idx
        if cidx >= 0:
            self.hovered_child = cidx
            self.selected = cidx
            self._hover_timer.stop()
        else:
            self.hovered_child = -1
            if self.open_child_index != idx:
                if self.open_child_index >= 0:
                    self.open_child_index = -1
                    self.search_edit.hide()
                    self._refresh_search_state()
                    self.selected = idx
                self._hover_timer.stop()
                if self.sectors[idx].get("children"):
                    self._hover_timer.start(self.cfg["hover_delay_ms"])
            if self.open_child_index < 0:
                self.selected = idx
        self.update()

    def _open_hovered(self):
        if self.hovered < 0 or self.hovered >= len(self.sectors):
            return
        if self.open_child_index >= 0 and self.open_child_index != self.hovered:
            return
        sector = self.sectors[self.hovered]
        if sector.get("children"):
            self.open_child_index = self.hovered
            self.selected = 0
            self.hovered_child = -1
            self._refresh_search_state()
            self.update()

    def _activate_current(self):
        items = self.current_items()
        if not items:
            return
        idx = min(self.selected, len(items) - 1)
        if idx < 0:
            return
        item = items[idx]
        if item.get("children"):
            self.open_child_index = self.selected
            self.selected = 0
            self.hovered = -1
            self._refresh_search_state()
            self.update()
        else:
            self.itemActivated.emit(item)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            if event.button() == Qt.RightButton:
                self.close_menu()
            return
        x, y = event.pos().x(), event.pos().y()
        dx = x - self._cx
        dy = y - self._cy
        dist = math.hypot(dx, dy)
        if dist <= self.r_in - 6:
            if self.edit_mode:
                self.addFavoriteRequested.emit()
            elif self._search_mode():
                self.search_edit.setFocus()
            else:
                items = self.current_items()
                if items and 0 <= self.selected < len(items):
                    item = items[self.selected]
                    if item.get("children"):
                        self._activate_current()
            return
        idx, cidx = self._sector_at(x, y)
        if cidx >= 0:
            self.selected = cidx
            item = self.current_items()[cidx]
            if item.get("children"):
                self._activate_current()
            else:
                self.itemActivated.emit(item)
            return
        if idx >= 0 and self.open_child_index < 0 and self.r_in <= dist <= self.r_out:
            self.selected = idx
            self._activate_current()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Escape,):
            self.close_menu()
            return
        if key == Qt.Key_F2:
            self.edit_mode = not self.edit_mode
            self.update()
            return
        if key == Qt.Key_Delete and self.edit_mode:
            items = self.current_items()
            if items and 0 <= self.selected < len(items):
                item = items[self.selected]
                if item.get("favorite"):
                    self.removeFavoriteRequested.emit(item)
            return
        items = self.current_items()
        if not items:
            event.accept()
            return
        count = len(items)
        if key in (Qt.Key_Left, Qt.Key_Right):
            self.selected = (self.selected + (1 if key == Qt.Key_Right else -1)) % count
            self.update()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._activate_current()
        elif key == Qt.Key_Backspace:
            if self.open_child_index >= 0:
                parent_idx = self.open_child_index
                self.open_child_index = -1
                self.selected = parent_idx
                self.search_edit.hide()
                self._refresh_search_state()
                self.update()
        else:
            text = event.text()
            if text.isdigit():
                num = int(text)
                if 1 <= num <= count:
                    self.selected = num - 1
                    self._activate_current()
            else:
                super().keyPressEvent(event)
        event.accept()
