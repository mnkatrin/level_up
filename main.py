import os
import shutil
import sys
import traceback

import pymysql
from PyQt6 import uic
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel,
                             QHBoxLayout, QVBoxLayout, QListWidgetItem,
                             QMessageBox, QSizePolicy, QFileDialog)


def exception_hook(extype, value, tb):
    traceback.print_exception(extype, value, tb)
    QMessageBox.critical(None, 'Ошибка', str(value))


def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='footwear_store',
        cursorclass=pymysql.cursors.DictCursor
    )


class ProductWidget(QWidget):
    def __init__(self, data: dict, thumb_size: int = 80):
        super().__init__()
        self.product_id = data['id']

        discount = int(data['discount']) if data['discount'] is not None else 0
        quantity = int(data['quantity']) if data['quantity'] is not None else 0

        h = QHBoxLayout(self)

        pix_label = QLabel()
        pix_label.setFixedSize(QSize(thumb_size, thumb_size))
        pix_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        pix = QPixmap(str(data['image'])) if data.get('image') else QPixmap()
        if pix.isNull():
            pix = QPixmap('picture.png')
        pix = pix.scaled(thumb_size, thumb_size,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        pix_label.setPixmap(pix)
        h.addWidget(pix_label)

        v = QVBoxLayout()
        v.addWidget(QLabel(f"{data['category_name']} | {data['product_name']}"))

        desc = QLabel('Описание: ' + str(data['description'] or ''))
        desc.setWordWrap(True)
        v.addWidget(desc)

        v.addWidget(QLabel('Производитель: ' + str(data['manufacturer_name'])))
        v.addWidget(QLabel('Поставщик: ' + str(data['vendor_name'])))

        price_row = QHBoxLayout()
        price_label = QLabel('Цена: ' + str(data['price']) + ' руб.')
        if discount > 0:
            price_label.setStyleSheet('text-decoration: line-through; color: red;')
            final = float(data['price']) - float(data['price']) * discount / 100
            final_label = QLabel(f'{final:.2f} руб.')
            final_label.setStyleSheet('color: black;')
            price_row.addWidget(price_label)
            price_row.addWidget(final_label)
        else:
            price_row.addWidget(price_label)
        price_row.addStretch()
        v.addLayout(price_row)

        v.addWidget(QLabel('Размер: ' + str(data['size'])))
        v.addWidget(QLabel('Количество на складе: ' + str(data['quantity'])))
        h.addLayout(v)
        h.addWidget(QLabel(str(discount) + '%'))


def fetch_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.article, p.product_name, p.size, p.price,
               p.discount, p.quantity, p.description, p.image,
               v.vendor_name, m.manufacturer_name, c.category_name
        FROM products p
        JOIN vendors v ON p.vendor_id = v.id
        JOIN manufacturers m ON p.manufacturer_id = m.id
        JOIN categories c ON p.category_id = c.id
    ''')
    products = cursor.fetchall()
    conn.close()
    return products


def fill_list(list_widget, products):
    list_widget.clear()
    for product in products:
        discount = int(product['discount']) if product['discount'] is not None else 0
        quantity = int(product['quantity']) if product['quantity'] is not None else 0

        widget = ProductWidget(product)
        item = QListWidgetItem()
        item.setSizeHint(widget.sizeHint())

        if quantity == 0:
            item.setBackground(QColor('#ADD8E6'))
        elif discount > 15:
            item.setBackground(QColor('#2E8B57'))

        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)



class ProductForm(QWidget):
    def __init__(self, parent_admin, product_id=None):
        super().__init__()
        uic.loadUi('product_form.ui', self)

        self.parent_admin = parent_admin
        self.product_id = product_id
        self._new_image_path = None
        self._old_image_path = None

        self._load_references()

        if product_id is None:
            self.lb_id.hide()
            self.le_id.hide()
            self._load_placeholder()
        else:
            self._load_product(product_id)

        self.pb_choose_photo.clicked.connect(self._choose_photo)
        self.pb_save.clicked.connect(self._save)
        self.pb_cancel.clicked.connect(self.close)

        self.setWindowModality(Qt.WindowModality.ApplicationModal)

    def _load_references(self):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute('SELECT id, category_name FROM categories ORDER BY category_name')
        self._categories = cur.fetchall()
        for row in self._categories:
            self.cb_category.addItem(row['category_name'], row['id'])

        cur.execute('SELECT id, manufacturer_name FROM manufacturers ORDER BY manufacturer_name')
        self._manufacturers = cur.fetchall()
        for row in self._manufacturers:
            self.cb_manufacturer.addItem(row['manufacturer_name'], row['id'])

        cur.execute('SELECT id, vendor_name FROM vendors ORDER BY vendor_name')
        self._vendors = cur.fetchall()
        for row in self._vendors:
            self.cb_vendor.addItem(row['vendor_name'], row['id'])

        conn.close()

    def _load_placeholder(self):
        pix = QPixmap('picture.png')
        if not pix.isNull():
            self.lb_photo.setPixmap(
                pix.scaled(150, 100, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation))

    def _load_product(self, product_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT p.*, v.vendor_name, m.manufacturer_name, c.category_name,
                   p.vendor_id, p.manufacturer_id, p.category_id
            FROM products p
            JOIN vendors v ON p.vendor_id = v.id
            JOIN manufacturers m ON p.manufacturer_id = m.id
            JOIN categories c ON p.category_id = c.id
            WHERE p.id = %s
        ''', (product_id,))
        p = cur.fetchone()
        conn.close()

        if not p:
            QMessageBox.warning(self, 'Ошибка', 'Товар не найден')
            self.close()
            return

        self.le_id.setText(str(p['id']))
        self.le_name.setText(str(p['product_name'] or ''))
        self.te_description.setPlainText(str(p['description'] or ''))
        self.le_size.setText(str(p['size'] or ''))
        self.dsb_price.setValue(float(p['price'] or 0))
        self.sb_quantity.setValue(int(p['quantity'] or 0))
        self.sb_discount.setValue(int(p['discount'] or 0))

        idx = self.cb_category.findData(p['category_id'])
        if idx >= 0:
            self.cb_category.setCurrentIndex(idx)

        idx = self.cb_manufacturer.findData(p['manufacturer_id'])
        if idx >= 0:
            self.cb_manufacturer.setCurrentIndex(idx)

        idx = self.cb_vendor.findData(p['vendor_id'])
        if idx >= 0:
            self.cb_vendor.setCurrentIndex(idx)

        self._old_image_path = p['image']
        pix = QPixmap(str(p['image'])) if p.get('image') else QPixmap()
        if pix.isNull():
            pix = QPixmap('picture.png')
        self.lb_photo.setPixmap(
            pix.scaled(150, 100, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation))

    def _choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите изображение', '',
            'Изображения (*.png *.jpg *.jpeg *.bmp *.gif)'
        )
        if not path:
            return
        self._new_image_path = path
        pix = QPixmap(path)
        self.lb_photo.setPixmap(
            pix.scaled(150, 100, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation))

    def _save(self):
        name = self.le_name.text().strip()
        if not name:
            QMessageBox.warning(self, 'Ошибка', 'Введите наименование товара')
            return

        price = self.dsb_price.value()
        if price < 0:
            QMessageBox.warning(self, 'Ошибка', 'Цена не может быть отрицательной')
            return

        quantity = self.sb_quantity.value()
        if quantity < 0:
            QMessageBox.warning(self, 'Ошибка', 'Количество не может быть отрицательным')
            return

        category_id = self.cb_category.currentData()
        manufacturer_id = self.cb_manufacturer.currentData()
        vendor_id = self.cb_vendor.currentData()
        description = self.te_description.toPlainText().strip()
        size = self.le_size.text().strip()
        discount = self.sb_discount.value()

        image_path = self._old_image_path

        if self._new_image_path:
            ext = os.path.splitext(self._new_image_path)[1]
            if self.product_id:
                dest_name = f'product_{self.product_id}{ext}'
            else:
                dest_name = f'product_new_{os.path.basename(self._new_image_path)}'
            dest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), dest_name)

            pix = QPixmap(self._new_image_path)
            pix = pix.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            pix.save(dest_path)

            if self._old_image_path and self._old_image_path != dest_path:
                old = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   self._old_image_path)
                if os.path.exists(old) and old != dest_path:
                    try:
                        os.remove(old)
                    except Exception:
                        pass

            image_path = dest_name

        conn = get_connection()
        cur = conn.cursor()

        if self.product_id is None:
            cur.execute('SELECT MAX(id) as max_id FROM products')
            row = cur.fetchone()
            new_id = (row['max_id'] or 0) + 1

            cur.execute('''
                INSERT INTO products
                    (id, product_name, category_id, description, manufacturer_id,
                     vendor_id, price, size, quantity, discount, image, article)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (new_id, name, category_id, description, manufacturer_id,
                  vendor_id, price, size, quantity, discount, image_path,
                  f'ART{new_id:04d}'))

            if self._new_image_path and image_path and 'product_new_' in image_path:
                ext = os.path.splitext(image_path)[1]
                final_name = f'product_{new_id}{ext}'
                old_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path)
                new_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), final_name)
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
                cur.execute('UPDATE products SET image = %s WHERE id = %s',
                            (final_name, new_id))
        else:
            cur.execute('''
                UPDATE products
                SET product_name = %s, category_id = %s, description = %s,
                    manufacturer_id = %s, vendor_id = %s, price = %s,
                    size = %s, quantity = %s, discount = %s, image = %s
                WHERE id = %s
            ''', (name, category_id, description, manufacturer_id,
                  vendor_id, price, size, quantity, discount,
                  image_path, self.product_id))

        conn.commit()
        conn.close()

        self.parent_admin.refresh_products()
        self.close()

class SearchFilterMixin:
    SEARCH_FIELDS = [
        'product_name', 'description', 'manufacturer_name',
        'vendor_name', 'category_name', 'article', 'size'
    ]

    def init_search_filter(self):
        self._all_products = fetch_products()

        vendors = sorted({p['vendor_name'] for p in self._all_products})
        self.cb_vendor.addItem('Все поставщики')
        for v in vendors:
            self.cb_vendor.addItem(v)

        self.cb_sort.addItem('Без сортировки')
        self.cb_sort.addItem('Количество ↑')
        self.cb_sort.addItem('Количество ↓')

        self.le_search.textChanged.connect(self.apply_filters)
        self.cb_vendor.currentIndexChanged.connect(self.apply_filters)
        self.cb_sort.currentIndexChanged.connect(self.apply_filters)
        self.pb_show_all.clicked.connect(self.show_all)

        self.apply_filters()

    def refresh_products(self):
        self._all_products = fetch_products()
        current_vendor = self.cb_vendor.currentText()
        self.cb_vendor.blockSignals(True)
        self.cb_vendor.clear()
        self.cb_vendor.addItem('Все поставщики')
        vendors = sorted({p['vendor_name'] for p in self._all_products})
        for v in vendors:
            self.cb_vendor.addItem(v)
        idx = self.cb_vendor.findText(current_vendor)
        self.cb_vendor.setCurrentIndex(idx if idx >= 0 else 0)
        self.cb_vendor.blockSignals(False)
        self.apply_filters()

    def show_all(self):
        self.le_search.blockSignals(True)
        self.cb_vendor.blockSignals(True)
        self.cb_sort.blockSignals(True)

        self.le_search.clear()
        self.cb_vendor.setCurrentIndex(0)
        self.cb_sort.setCurrentIndex(0)

        self.le_search.blockSignals(False)
        self.cb_vendor.blockSignals(False)
        self.cb_sort.blockSignals(False)

        fill_list(self.lw_products, self._all_products)

    def apply_filters(self):
        search = self.le_search.text().strip().lower()
        vendor = self.cb_vendor.currentText()
        sort_idx = self.cb_sort.currentIndex()

        result = self._all_products

        if vendor != 'Все поставщики':
            result = [p for p in result if p['vendor_name'] == vendor]

        if search:
            filtered = []
            for p in result:
                for field in self.SEARCH_FIELDS:
                    val = str(p.get(field) or '').lower()
                    if search in val:
                        filtered.append(p)
                        break
            result = filtered

        if sort_idx == 1:
            result = sorted(result, key=lambda p: int(p['quantity'] or 0))
        elif sort_idx == 2:
            result = sorted(result, key=lambda p: int(p['quantity'] or 0), reverse=True)

        fill_list(self.lw_products, result)


class Guest(QMainWindow):
    def __init__(self, login_window):
        super().__init__()
        uic.loadUi('guest.ui', self)
        self.login_window = login_window
        self.pb_exit.clicked.connect(self.exit)
        fill_list(self.lw_products, fetch_products())

    def exit(self):
        self.login_window.show()
        self.close()


class Client(QMainWindow):
    def __init__(self, user: dict, login_window):
        super().__init__()
        uic.loadUi('client.ui', self)
        self.login_window = login_window
        self.lb_fio.setText(f"{user['last_name']} {user['first_name']} {user['middle_name']}")
        self.pb_exit.clicked.connect(self.exit)
        fill_list(self.lw_products, fetch_products())

    def exit(self):
        self.login_window.show()
        self.close()


class Manager(SearchFilterMixin, QMainWindow):
    def __init__(self, user: dict, login_window):
        super().__init__()
        uic.loadUi('manager.ui', self)
        self.login_window = login_window
        self.lb_fio.setText(f"{user['last_name']} {user['first_name']} {user['middle_name']}")
        self.pb_exit.clicked.connect(self.exit)
        self.init_search_filter()

    def exit(self):
        self.login_window.show()
        self.close()


class Admin(SearchFilterMixin, QMainWindow):
    def __init__(self, user: dict, login_window):
        super().__init__()
        uic.loadUi('admin.ui', self)
        self.login_window = login_window
        self.lb_fio.setText(f"{user['last_name']} {user['first_name']} {user['middle_name']}")
        self.pb_exit.clicked.connect(self.exit)
        self._edit_window = None
        self.init_search_filter()

        self.pb_add.clicked.connect(self._add_product)
        self.pb_delete.clicked.connect(self._delete_product)
        self.lw_products.itemDoubleClicked.connect(self._edit_product)

    def _add_product(self):
        if self._edit_window is not None and self._edit_window.isVisible():
            self._edit_window.activateWindow()
            return
        self._edit_window = ProductForm(self, product_id=None)
        self._edit_window.setWindowTitle('Добавить товар')
        self._edit_window.show()

    def _edit_product(self, item):
        if self._edit_window is not None and self._edit_window.isVisible():
            self._edit_window.activateWindow()
            return
        widget = self.lw_products.itemWidget(item)
        if widget is None:
            return
        product_id = widget.product_id
        self._edit_window = ProductForm(self, product_id=product_id)
        self._edit_window.setWindowTitle(f'Редактировать товар (ID: {product_id})')
        self._edit_window.show()

    def _delete_product(self):
        item = self.lw_products.currentItem()
        if item is None:
            QMessageBox.warning(self, 'Удаление', 'Выберите товар для удаления')
            return

        widget = self.lw_products.itemWidget(item)
        if widget is None:
            return
        product_id = widget.product_id

        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) as cnt FROM order_items WHERE order_id = %s',
                    (product_id,))
        row = cur.fetchone()
        if row and row['cnt'] > 0:
            conn.close()
            QMessageBox.warning(self, 'Удаление',
                                'Нельзя удалить товар, который присутствует в заказе')
            return

        reply = QMessageBox.question(
            self, 'Подтверждение',
            'Вы уверены, что хотите удалить этот товар?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            conn.close()
            return

        cur.execute('SELECT image FROM products WHERE id = %s', (product_id,))
        prod = cur.fetchone()
        image_path = prod['image'] if prod else None

        cur.execute('DELETE FROM products WHERE id = %s', (product_id,))
        conn.commit()
        conn.close()

        if image_path:
            full = os.path.join(os.path.dirname(os.path.abspath(__file__)), image_path)
            if os.path.exists(full):
                try:
                    os.remove(full)
                except Exception:
                    pass

        self.refresh_products()

    def exit(self):
        self.login_window.show()
        self.close()


class Login(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi('login.ui', self)
        self.pb_login.clicked.connect(self.login)
        self.pb_guest.clicked.connect(self.guest)

    def login(self):
        login = self.le_login.text()
        password = self.le_password.text()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM users WHERE login = %s AND password = %s',
            (login, password)
        )
        user = cursor.fetchone()
        conn.close()

        if not user:
            QMessageBox.warning(self, 'Ошибка', 'Неверный логин или пароль')
            return

        role = user['role']
        if role == 'Администратор':
            self.window = Admin(user, self)
        elif role == 'Менеджер':
            self.window = Manager(user, self)
        elif role == 'Клиент':
            self.window = Client(user, self)
        else:
            QMessageBox.warning(self, 'Ошибка', f'Неизвестная роль: {role}')
            return

        self.window.show()
        self.hide()
        self.le_password.clear()
        self.le_login.clear()

    def guest(self):
        self.window = Guest(self)
        self.window.show()
        self.hide()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    sys.excepthook = exception_hook
    window = Login()
    window.show()
    sys.exit(app.exec())
