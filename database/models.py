from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='mechanic')
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(255), default='default_avatar.png')  # Путь к аватарке
    bio = db.Column(db.Text)  # Краткая информация о пользователе
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Связь с сотрудником
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.employee_id'))
    #employee = db.relationship('Employee', backref='user_account')


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_role_name(self):
        from config import Config
        return Config.ROLES.get(self.role, self.role)


class Client(db.Model):
    __tablename__ = 'client'

    client_id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(100))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    # Только одна связь с автомобилями
    cars = db.relationship('Car', backref='owner', lazy=True, cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"


class Car(db.Model):
    __tablename__ = 'car'

    car_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.client_id'), nullable=False)
    brand = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer)
    license_plate = db.Column(db.String(20), nullable=False, unique=True)
    vin = db.Column(db.String(17), unique=True)

    # Связи (без сложных условий)
    orders = db.relationship('ServiceOrder', backref='car', lazy=True, cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f"{self.brand} {self.model} ({self.license_plate})"

class ServiceOrder(db.Model):
    __tablename__ = 'service_order'

    order_id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.car_id'), nullable=False)
    reception_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    completion_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='принят')
    total_cost = db.Column(db.Numeric(10, 2), default=0.00)
    notes = db.Column(db.Text)

    # Связи
    order_items = db.relationship('OrderComposition', backref='order_info', lazy=True, cascade='all, delete-orphan')

    def get_status_name(self):
        from config import Config
        return Config.ORDER_STATUSES.get(self.status, self.status)

    # В классе ServiceOrder заменяем метод calculate_total на исправленный:

    def calculate_total(self):
        """Пересчитывает общую стоимость заказа"""
        total = 0.0

        # Суммируем стоимость работ
        for item in self.order_items:
            work_cost = 0.0

            # 1. Пробуем получить стоимость из actual_cost
            if item.actual_cost is not None:
                work_cost = float(item.actual_cost)
            # 2. Если actual_cost нет, берем base_cost из work_info
            elif item.work_info and item.work_info.base_cost is not None:
                work_cost = float(item.work_info.base_cost)
            # 3. Если work_info не доступен, проверяем связанную работу
            else:
                # Пытаемся получить работу через SQLAlchemy
                from database.models import ServiceWork
                work = ServiceWork.query.get(item.work_id)
                if work and work.base_cost is not None:
                    work_cost = float(work.base_cost)

            # Для отладки (можно удалить после исправления)
            print(f"DEBUG: Работа ID {item.work_id}, стоимость: {work_cost}, статус: {item.work_status}")

            total += work_cost

            # Суммируем стоимость запчастей для этой работы
            for part_usage in item.parts_used:
                if part_usage.unit_price_at_time is not None and part_usage.quantity is not None:
                    part_total = float(part_usage.unit_price_at_time) * int(part_usage.quantity)
                    total += part_total

        self.total_cost = total
        return total

    def update_total(self):
        """Обновляет общую стоимость заказа и сохраняет в БД"""
        total = self.calculate_total()
        db.session.add(self)
        db.session.commit()
        return total


class ServiceWork(db.Model):
    __tablename__ = 'service_work'

    work_id = db.Column(db.Integer, primary_key=True)
    work_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    standard_hours = db.Column(db.Numeric(5, 2))
    base_cost = db.Column(db.Numeric(10, 2), nullable=False)

    # Связи
    order_items = db.relationship('OrderComposition', backref='work_info', lazy=True)


class Employee(db.Model):
    __tablename__ = 'employee'

    employee_id = db.Column(db.Integer, primary_key=True)
    last_name = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    hire_date = db.Column(db.Date, default=datetime.utcnow)
    previous_experience = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    # Связи
    user = db.relationship('User', backref='employee_info', uselist=False)
    assigned_works = db.relationship('OrderComposition', backref='assigned_employee', lazy=True)

    @property
    def user_account(self):
        """Возвращает учетную запись пользователя, связанную с сотрудником"""
        from database.models import User
        return User.query.filter_by(employee_id=self.employee_id).first()

    @property
    def has_user_account(self):
        """Проверяет, есть ли у сотрудника учетная запись"""
        return self.user_account is not None

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"

    @property
    def work_experience(self):
        """Общий стаж работы (предыдущий + в автосервисе)"""
        total_experience = self.previous_experience or 0

        # Добавляем стаж работы в автосервисе
        if self.hire_date:
            today = datetime.now().date()
            service_experience = today.year - self.hire_date.year

            # Корректируем, если дата найма еще не наступила в этом году
            if today.month < self.hire_date.month or (
                    today.month == self.hire_date.month and today.day < self.hire_date.day):
                service_experience -= 1

            total_experience += service_experience

        return max(0, total_experience)  # Обеспечиваем неотрицательное значение

    @property
    def service_experience(self):
        """Стаж работы только в этом автосервисе"""
        if self.hire_date:
            today = datetime.now().date()
            experience = today.year - self.hire_date.year

            if today.month < self.hire_date.month or (
                    today.month == self.hire_date.month and today.day < self.hire_date.day):
                experience -= 1

            return max(0, experience)
        return 0

    @property
    def current_assignments_count(self):
        """Количество текущих назначений"""
        from database.models import OrderComposition
        return OrderComposition.query.filter(
            OrderComposition.employee_id == self.employee_id,
            OrderComposition.work_status.in_(['назначена', 'в работе'])
        ).count()

    @property
    def completed_works_count(self):
        """Количество завершенных работ"""
        from database.models import OrderComposition
        return OrderComposition.query.filter(
            OrderComposition.employee_id == self.employee_id,
            OrderComposition.work_status == 'завершена'
        ).count()


class SparePart(db.Model):
    __tablename__ = 'spare_part'

    part_id = db.Column(db.Integer, primary_key=True)
    part_name = db.Column(db.String(100), nullable=False)
    part_number = db.Column(db.String(50))
    manufacturer = db.Column(db.String(100))
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity_in_stock = db.Column(db.Integer, default=0)
    min_quantity = db.Column(db.Integer, default=5)
    location = db.Column(db.String(50))

    # Связи
    usage_records = db.relationship('PartsUsage', backref='part_info', lazy=True)


class OrderComposition(db.Model):
    __tablename__ = 'order_composition'

    order_comp_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('service_order.order_id'), nullable=False)
    work_id = db.Column(db.Integer, db.ForeignKey('service_work.work_id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.employee_id'))
    actual_hours = db.Column(db.Numeric(5, 2))
    actual_cost = db.Column(db.Numeric(10, 2))
    work_status = db.Column(db.String(20), default='назначена')
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # Связи
    parts_used = db.relationship('PartsUsage', backref='composition_info', lazy=True, cascade='all, delete-orphan')

    def get_status_name(self):
        from config import Config
        return Config.WORK_STATUSES.get(self.work_status, self.work_status)

    def can_be_completed_by(self, user):
        """Проверяет, может ли пользователь завершить эту работу"""
        if user.role == 'mechanic':
            return self.employee_id == user.employee_id and self.work_status != 'завершена'
        elif user.role in ['admin', 'master']:
            return self.work_status != 'завершена'
        return False

    @property
    def completion_date_display(self):
        """Дата выполнения для отображения"""
        if self.end_time:
            return self.end_time.strftime('%d.%m.%Y %H:%M')
        elif self.start_time:
            return f"Начата: {self.start_time.strftime('%d.%m.%Y %H:%M')}"
        else:
            return "Не начата"


class PartsUsage(db.Model):
    __tablename__ = 'parts_usage'

    usage_id = db.Column(db.Integer, primary_key=True)
    order_comp_id = db.Column(db.Integer, db.ForeignKey('order_composition.order_comp_id'), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey('spare_part.part_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price_at_time = db.Column(db.Numeric(10, 2))

    # Связи
    # part_info создается автоматически через backref в SparePart

    @property
    def part(self):
        """Алиас для part_info для совместимости со старым кодом"""
        return self.part_info

    @property
    def total_price(self):
        """Общая стоимость за количество"""
        if self.unit_price_at_time:
            return self.quantity * self.unit_price_at_time
        return 0

# Класс WorkAssignment временно удален для упрощения