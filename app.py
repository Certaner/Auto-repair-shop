from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bootstrap import Bootstrap4
from werkzeug.utils import secure_filename
from sqlalchemy import exc
from config import Config
from database.models import db, User, Client, Car, ServiceOrder, Employee, ServiceWork, SparePart, OrderComposition, PartsUsage
from database.session import login_manager
from database.db_init import init_db
from datetime import datetime, date
import os
import uuid
import logging
logging.basicConfig(level=logging.DEBUG)

# Импорт utils для генерации PDF
from utils.pdf_generator import generate_order_invoice

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация расширений
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
bootstrap = Bootstrap4(app)

# Создание папок
os.makedirs('static/uploads', exist_ok=True)

@app.context_processor
def inject_now():
    return {
        'now': datetime.now,
        'date': date,  # Добавляем модуль date
        'current_year': datetime.now().year
    }

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if user.is_active:
                login_user(user)
                user.last_login = datetime.utcnow()  # Добавьте эту строку
                db.session.commit()
                flash('Вы успешно вошли в систему!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Ваш аккаунт деактивирован.', 'danger')
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')

    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    stats = {}
    recent_orders = []
    my_assigned_works = []
    show_general_stats = False

    # Общая статистика для админов, менеджеров и мастеров
    if current_user.role in ['admin', 'manager', 'master']:
        show_general_stats = True
        stats['total_clients'] = Client.query.count()
        stats['total_orders'] = ServiceOrder.query.count()
        stats['active_orders'] = ServiceOrder.query.filter_by(status='в работе').count()

        # Получаем выручку за текущий месяц
        first_day_of_month = datetime.now().replace(day=1)
        completed_orders = ServiceOrder.query.filter(
            ServiceOrder.status == 'завершен',
            ServiceOrder.completion_date >= first_day_of_month
        ).all()

        stats['month_revenue'] = sum(float(order.total_cost) for order in completed_orders)

        # Получаем последние 5 заказов
        recent_orders = ServiceOrder.query.order_by(ServiceOrder.reception_date.desc()).limit(5).all()

    # Дополнительная статистика для механиков
    elif current_user.role == 'mechanic':
        # Для механиков
        from database.models import OrderComposition

        # Статистика по работам механика
        stats['assigned_works'] = OrderComposition.query.filter(
            OrderComposition.employee_id == current_user.employee_id,
            OrderComposition.work_status.in_(['назначена', 'в работе'])
        ).count()

        stats['completed_works'] = OrderComposition.query.filter(
            OrderComposition.employee_id == current_user.employee_id,
            OrderComposition.work_status == 'завершена'
        ).count()

        stats['total_works'] = OrderComposition.query.filter_by(
            employee_id=current_user.employee_id
        ).count()

        # Последние 10 назначенных работ (вместо 5)
        my_assigned_works = OrderComposition.query.filter_by(
            employee_id=current_user.employee_id
        ).order_by(OrderComposition.order_comp_id.desc()).limit(10).all()

        # Последние заказы, в которых есть работы механика
        if my_assigned_works:
            order_ids = set(work.order_id for work in my_assigned_works)
            recent_orders = ServiceOrder.query.filter(
                ServiceOrder.order_id.in_(list(order_ids))
            ).order_by(ServiceOrder.reception_date.desc()).limit(3).all()

    return render_template('dashboard/index.html',
                           stats=stats,
                           recent_orders=recent_orders,
                           my_assigned_works=my_assigned_works,
                           show_general_stats=show_general_stats)


# Роуты для работы с клиентами
@app.route('/clients')
@login_required
def clients_list():
    if current_user.role not in ['admin', 'master', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    clients = Client.query.order_by(Client.last_name).all()
    return render_template('clients/list.html', clients=clients)


@app.route('/clients/add', methods=['GET', 'POST'])
@login_required
def add_client():
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        client = Client(
            last_name=request.form.get('last_name'),
            first_name=request.form.get('first_name'),
            phone=request.form.get('phone'),
            email=request.form.get('email')
        )
        db.session.add(client)
        db.session.commit()
        flash('Клиент успешно добавлен!', 'success')
        return redirect(url_for('clients_list'))

    return render_template('clients/add.html')


@app.route('/clients/<int:client_id>')
@login_required
def client_details(client_id):
    if current_user.role not in ['admin', 'master', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    client = Client.query.get_or_404(client_id)
    return render_template('clients/details.html', client=client)

@app.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    client = Client.query.get_or_404(client_id)

    if request.method == 'POST':
        new_phone = request.form.get('phone')

        # Проверяем, не используется ли телефон другим клиентом
        if new_phone != client.phone:
            existing_client = Client.query.filter_by(phone=new_phone).first()
            if existing_client:
                flash('Этот телефон уже используется другим клиентом.', 'danger')
                return render_template('clients/edit.html', client=client)

        client.last_name = request.form.get('last_name')
        client.first_name = request.form.get('first_name')
        client.phone = new_phone
        client.email = request.form.get('email')

        db.session.commit()
        flash('Данные клиента успешно обновлены!', 'success')
        return redirect(url_for('client_details', client_id=client_id))

    return render_template('clients/edit.html', client=client)

# Роуты для работы с сотрудниками
@app.route('/employees')
@login_required
def employees_list():
    if current_user.role not in ['admin', 'manager', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    employees = Employee.query.order_by(Employee.last_name, Employee.first_name).all()
    return render_template('employees/list.html', employees=employees)


def generate_username(first_name, last_name):
    """Генерация логина на основе имени и фамилии"""
    import re

    # Транслитерация
    def translit(text):
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'shch', 'ы': 'y', 'э': 'e', 'ю': 'yu',
            'я': 'ya'
        }
        result = ''
        for char in text.lower():
            result += translit_map.get(char, char)
        return result

    login_base = translit(last_name.lower()) + translit(first_name.lower()[0])
    login_base = re.sub(r'[^a-z0-9_]', '', login_base)

    return login_base

@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        prev_exp = request.form.get('previous_experience', '0')
        try:
            previous_experience = int(prev_exp)
        except ValueError:
            previous_experience = 0

        employee = Employee(
            last_name=request.form.get('last_name'),
            first_name=request.form.get('first_name'),
            position=request.form.get('position'),
            phone=request.form.get('phone'),
            hire_date=datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d') if request.form.get(
                'hire_date') else datetime.now().date(),
            previous_experience=int(request.form.get('previous_experience', 0)),
            is_active=request.form.get('is_active') == 'on'
        )

        db.session.add(employee)
        db.session.flush()  # Получаем employee_id

        # Автоматическое создание учетной записи для определенных должностей
        position = employee.position.lower()
        create_account = request.form.get('create_account') == 'on'

        user_created = None

        if create_account:
            # Определяем роль
            if 'мастер' in position or 'приёмщик' in position:
                role = 'master'
            elif 'механик' in position:
                role = 'mechanic'
            elif 'кладовщик' in position:
                role = 'storekeeper'
            elif 'менеджер' in position or 'руководитель' in position:
                role = 'manager'
            else:
                role = 'mechanic'  # по умолчанию

            # Генерируем уникальный логин
            username_base = generate_username(employee.first_name, employee.last_name)
            counter = 1
            username = username_base

            while User.query.filter_by(username=username).first():
                username = f"{username_base}{counter}"
                counter += 1

            # Генерируем временный пароль
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for _ in range(8))

            # Создаем пользователя
            user = User(
                username=username,
                email=f"{username}@autoservice.ru",
                full_name=employee.full_name,
                role=role,
                employee_id=employee.employee_id,
                is_active=True
            )
            user.set_password(password)

            db.session.add(user)
            user_created = {
                'username': username,
                'password': password,
                'role': role
            }

        db.session.commit()

        if user_created:
            flash(f'Сотрудник {employee.full_name} успешно добавлен! '
                  f'Создана учетная запись: {user_created["username"]} / {user_created["password"]}',
                  'success')
        else:
            flash(f'Сотрудник {employee.full_name} успешно добавлен!', 'success')

        return redirect(url_for('employees_list'))

    return render_template('employees/add.html')


@app.route('/employees/<int:employee_id>')
@login_required
def employee_details(employee_id):
    if current_user.role not in ['admin', 'manager', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    employee = Employee.query.get_or_404(employee_id)
    return render_template('employees/details.html', employee=employee)


@app.route('/employees/<int:employee_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    employee = Employee.query.get_or_404(employee_id)

    if request.method == 'POST':
        employee.last_name = request.form.get('last_name')
        employee.first_name = request.form.get('first_name')
        employee.position = request.form.get('position')
        employee.phone = request.form.get('phone')

        prev_exp = request.form.get('previous_experience', '0')
        try:
            employee.previous_experience = int(prev_exp)
        except ValueError:
            employee.previous_experience = 0

        if request.form.get('hire_date'):
            employee.hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d')

        employee.is_active = request.form.get('is_active') == 'on'

        db.session.commit()
        flash(f'Данные сотрудника {employee.full_name} успешно обновлены!', 'success')
        return redirect(url_for('employee_details', employee_id=employee_id))

    return render_template('employees/edit.html', employee=employee)


@app.route('/employees/<int:employee_id>/delete', methods=['POST'])
@login_required
def delete_employee(employee_id):
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    employee = Employee.query.get_or_404(employee_id)

    # Проверяем, не назначен ли сотрудник на какие-либо работы
    active_assignments = OrderComposition.query.filter_by(employee_id=employee_id).count()

    if active_assignments > 0:
        flash(f'Нельзя удалить сотрудника, который назначен на {active_assignments} работ.', 'danger')
        return redirect(url_for('employee_details', employee_id=employee_id))

    try:
        full_name = employee.full_name
        db.session.delete(employee)
        db.session.commit()
        flash(f'Сотрудник {full_name} успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении сотрудника: {str(e)}', 'danger')

    return redirect(url_for('employees_list'))


@app.route('/employees/<int:employee_id>/create_account', methods=['POST'])
@login_required
def create_employee_account(employee_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    employee = Employee.query.get_or_404(employee_id)

    # Проверяем, есть ли уже учетная запись
    existing_user = User.query.filter_by(employee_id=employee_id).first()
    if existing_user:
        flash(f'У сотрудника {employee.full_name} уже есть учетная запись: {existing_user.username}', 'warning')
        return redirect(url_for('employee_details', employee_id=employee_id))

    # Генерируем логин
    username_base = generate_username(employee.first_name, employee.last_name)
    counter = 1
    username = username_base

    while User.query.filter_by(username=username).first():
        username = f"{username_base}{counter}"
        counter += 1

    # Генерируем пароль
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(8))

    # Определяем роль
    position = employee.position.lower()
    if 'мастер' in position or 'приёмщик' in position:
        role = 'master'
    elif 'механик' in position:
        role = 'mechanic'
    elif 'кладовщик' in position:
        role = 'storekeeper'
    elif 'менеджер' in position or 'руководитель' in position:
        role = 'manager'
    else:
        role = 'mechanic'

    # Создаем пользователя
    user = User(
        username=username,
        email=f"{username}@autoservice.ru",
        full_name=employee.full_name,
        role=role,
        employee_id=employee.employee_id,
        is_active=employee.is_active
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    flash(f'Учетная запись создана: {username} / {password} (Роль: {role})', 'success')
    return redirect(url_for('employee_details', employee_id=employee_id))

# Роуты для работы с автомобилями
@app.route('/cars')
@login_required
def cars_list():
    if current_user.role not in ['admin', 'master', 'mechanic']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    cars = Car.query.join(Client).order_by(Client.last_name).all()
    return render_template('cars/list.html', cars=cars)


@app.route('/cars/add', methods=['GET', 'POST'])
@login_required
def add_car():
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    clients = Client.query.all()

    if request.method == 'POST':
        car = Car(
            client_id=request.form.get('client_id'),
            brand=request.form.get('brand'),
            model=request.form.get('model'),
            year=request.form.get('year'),
            license_plate=request.form.get('license_plate'),
            vin=request.form.get('vin')
        )
        db.session.add(car)
        db.session.commit()
        flash('Автомобиль успешно добавлен!', 'success')
        return redirect(url_for('cars_list'))

    return render_template('cars/add.html', clients=clients)


# Роуты для работы с заказами
@app.route('/orders')
@login_required
def orders_list():
    if current_user.role not in ['admin', 'master', 'mechanic', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    # Фильтрация в зависимости от роли
    if current_user.role == 'mechanic':
        # Механик видит только заказы, где он назначен на работы
        from database.models import OrderComposition

        # Получаем ID заказов, где механик назначен
        assigned_orders = OrderComposition.query.filter_by(
            employee_id=current_user.employee_id
        ).with_entities(OrderComposition.order_id).distinct().all()

        order_ids = [ao.order_id for ao in assigned_orders]

        if order_ids:
            orders = ServiceOrder.query.filter(
                ServiceOrder.order_id.in_(order_ids)
            ).order_by(ServiceOrder.reception_date.desc()).all()
        else:
            orders = []

    else:
        # Админы, мастера и менеджеры видят все заказы
        orders = ServiceOrder.query.order_by(ServiceOrder.reception_date.desc()).all()

    return render_template('orders/list.html', orders=orders)


@app.route('/orders/add', methods=['GET', 'POST'])
@login_required
def add_order():
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    cars = Car.query.join(Client).order_by(Client.last_name).all()
    works = ServiceWork.query.all()
    employees = Employee.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        order = ServiceOrder(
            car_id=request.form.get('car_id'),
            reception_date=datetime.strptime(request.form.get('reception_date'), '%Y-%m-%d'),
            notes=request.form.get('notes')
        )
        db.session.add(order)
        db.session.flush()  # Получаем order_id

        # Добавляем работы
        work_ids = request.form.getlist('work_ids[]')
        employee_ids = request.form.getlist('employee_ids[]')

        for i, work_id in enumerate(work_ids):
            # Получаем стоимость работы
            work = ServiceWork.query.get(work_id)
            work_cost = work.base_cost if work else 0

            order_item = OrderComposition(
                order_id=order.order_id,
                work_id=work_id,
                employee_id=employee_ids[i] if i < len(employee_ids) else None,
                actual_cost=work_cost  # Устанавливаем actual_cost сразу
            )
            db.session.add(order_item)

        db.session.commit()
        order.update_total()

        flash('Заказ-наряд успешно создан!', 'success')
        return redirect(url_for('order_details', order_id=order.order_id))

    return render_template('orders/add.html', cars=cars, works=works, employees=employees)


@app.route('/orders/<int:order_id>')
@login_required
def order_details(order_id):
    if current_user.role not in ['admin', 'master', 'mechanic', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)

    # Для механика проверяем, назначен ли он на работу в этом заказе
    if current_user.role == 'mechanic':
        from database.models import OrderComposition

        # Проверяем, есть ли работы в заказе, назначенные этому механику
        assigned_work = OrderComposition.query.filter_by(
            order_id=order_id,
            employee_id=current_user.employee_id
        ).first()

        if not assigned_work:
            flash('У вас нет доступа к этому заказу.', 'danger')
            return redirect(url_for('orders_list'))

    parts = SparePart.query.order_by(SparePart.part_name).all()

    return render_template('orders/details.html', order=order, parts=parts)


# Завершение работы механиком
@app.route('/orders/<int:order_id>/complete_work/<int:order_comp_id>', methods=['POST'])
@login_required
def complete_work(order_id, order_comp_id):
    # Проверяем, что пользователь - механик
    if current_user.role != 'mechanic':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    # Получаем заказ и работу
    order = ServiceOrder.query.get_or_404(order_id)
    work = OrderComposition.query.get_or_404(order_comp_id)

    # Проверяем, назначен ли механик на эту работу
    if work.employee_id != current_user.employee_id:
        flash('Вы не можете завершить эту работу - она назначена другому механику.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    # Проверяем, что работа еще не завершена
    if work.work_status == 'завершена':
        flash('Эта работа уже завершена.', 'info')
        return redirect(url_for('order_details', order_id=order_id))

    try:
        # Убедимся, что actual_cost установлен
        if work.actual_cost is None:
            # Получаем базовую стоимость работы
            from database.models import ServiceWork
            service_work = ServiceWork.query.get(work.work_id)
            if service_work:
                work.actual_cost = service_work.base_cost

        # Обновляем статус работы
        work.work_status = 'завершена'
        work.end_time = datetime.now()

        db.session.commit()

        # Обновляем общую стоимость заказа
        order.update_total()

        flash('Работа отмечена как выполненная!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении статуса работы: {str(e)}', 'danger')

    return redirect(url_for('order_details', order_id=order_id))


# Массовое завершение работ (для мастера)
@app.route('/orders/<int:order_id>/complete_all_works', methods=['POST'])
@login_required
def complete_all_works(order_id):
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    order = ServiceOrder.query.get_or_404(order_id)

    try:
        for work in order.order_items:
            if work.work_status != 'завершена':
                # Убедимся, что actual_cost установлен
                if work.actual_cost is None:
                    from database.models import ServiceWork
                    service_work = ServiceWork.query.get(work.work_id)
                    if service_work:
                        work.actual_cost = service_work.base_cost

                work.work_status = 'завершена'
                work.end_time = datetime.now()

        db.session.commit()

        # Обновляем общую стоимость заказа
        order.update_total()

        flash('Все работы по заказу отмечены как завершенные!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении статусов работ: {str(e)}', 'danger')

    return redirect(url_for('order_details', order_id=order_id))


@app.route('/orders/<int:order_id>/recalculate_work_costs', methods=['POST'])
@login_required
def recalculate_work_costs(order_id):
    """Восстанавливает стоимости работ в заказе"""
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    order = ServiceOrder.query.get_or_404(order_id)

    try:
        from database.models import ServiceWork

        updated_count = 0
        for item in order.order_items:
            # Если actual_cost не установлен, восстанавливаем из work_info
            if item.actual_cost is None:
                if item.work_info:
                    item.actual_cost = item.work_info.base_cost
                    updated_count += 1
                else:
                    # Ищем работу отдельно
                    work = ServiceWork.query.get(item.work_id)
                    if work:
                        item.actual_cost = work.base_cost
                        updated_count += 1

        db.session.commit()

        # Обновляем общую стоимость
        order.update_total()

        flash(f'Восстановлены стоимости для {updated_count} работ. Общая сумма: {order.total_cost} руб.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при восстановлении стоимостей: {str(e)}', 'danger')

    return redirect(url_for('order_details', order_id=order_id))

# Роут для изменения статуса заказа
@app.route('/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)
    new_status = request.form.get('new_status')
    comment = request.form.get('comment', '')

    if not new_status:
        flash('Не указан новый статус.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    valid_statuses = ['принят', 'в работе', 'ожидает запчастей', 'завершен', 'отменен']
    if new_status not in valid_statuses:
        flash(f'Недопустимый статус: {new_status}', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    try:
        old_status = order.status
        order.status = new_status

        # Если статус "завершен", обновляем дату завершения
        if new_status == 'завершен':
            order.completion_date = datetime.now().date()
            # Обновляем статусы всех работ в заказе
            for item in order.order_items:
                if item.work_status != 'завершена':
                    item.work_status = 'завершена'
                    item.end_time = datetime.now()

        # Пересчитываем общую стоимость
        order.update_total()  # Убедимся, что это здесь есть

        db.session.commit()

        flash(f'Статус заказа #{order_id} изменен с "{old_status}" на "{new_status}"', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении статуса: {str(e)}', 'danger')

    return redirect(url_for('order_details', order_id=order_id))


from flask import request  # Добавь этот импорт в начало app.py (если нет)

@app.route('/orders/<int:order_id>/add_parts', methods=['POST'])
@login_required
def add_parts_to_order(order_id):
    """Упрощенный и защищенный метод добавления запчастей"""

    # 1. Базовые проверки
    if current_user.role not in ['admin', 'master', 'mechanic']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)

    # 2. Проверка статуса заказа
    if order.status in ['завершен', 'отменен']:
        flash('Нельзя добавлять запчасти к завершенному или отмененному заказу.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    # 3. Получаем данные из формы
    order_comp_id = request.form.get('order_comp_id')
    part_id = request.form.get('part_id')

    try:
        quantity = int(request.form.get('quantity', 1))
        if quantity <= 0:
            flash('Количество должно быть положительным числом.', 'danger')
            return redirect(url_for('order_details', order_id=order_id))
    except ValueError:
        flash('Неверное количество.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    # 4. Для механиков - проверка доступа к работе
    if current_user.role == 'mechanic':
        if not order_comp_id:
            flash('Не указана работа.', 'danger')
            return redirect(url_for('order_details', order_id=order_id))

        from database.models import OrderComposition
        work_assignment = OrderComposition.query.filter_by(
            order_comp_id=order_comp_id,
            employee_id=current_user.employee_id
        ).first()

        if not work_assignment:
            flash('Вы не можете добавлять запчасти к этой работе.', 'danger')
            return redirect(url_for('order_details', order_id=order_id))

    # 5. Получаем информацию о запчасти (ТОЛЬКО ДЛЯ ЦЕНЫ)
    part = db.session.get(SparePart, part_id)
    if not part:
        flash('Запчасть не найдена.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    # 6. Используем InventoryManager для гарантированного однократного вычитания
    from inventory_utils import InventoryManager  # Импортируем наш менеджер

    success, message = InventoryManager.use_part(
        order_comp_id=order_comp_id,
        part_id=part_id,
        quantity=quantity,
        unit_price_at_time=part.unit_price
    )

    if success:
        # Перезагружаем заказ из БД, чтобы увидеть новые запчасти
        db.session.refresh(order)
        # Обновляем общую стоимость заказа
        order.update_total()
        db.session.commit()  # Сохраняем обновлённый total_cost, если метод не commit'ит сам
        flash(f'Запчасть "{part.part_name}" добавлена к работе. {message}', 'success')
    else:
        flash(f'Ошибка: {message}', 'danger')

    return redirect(url_for('order_details', order_id=order_id))

def mechanic_has_access_to_order(order_id, user_id):
    """Проверяет, имеет ли механик доступ к заказу"""
    from database.models import OrderComposition

    if current_user.role == 'mechanic':
        assigned_work = OrderComposition.query.filter_by(
            order_id=order_id,
            employee_id=current_user.employee_id
        ).first()
        return assigned_work is not None
    return True


@app.route('/debug/inventory/<int:part_id>')
@login_required
def debug_inventory(part_id):
    """Отладочный маршрут для проверки остатков"""
    if current_user.role != 'admin':
        return "Доступ запрещен", 403

    part = db.session.get(SparePart, part_id)
    if not part:
        return f"Запчасть {part_id} не найдена"

    # Проверяем логи операций
    logs = db.session.execute(
        text("SELECT * FROM inventory_log WHERE part_id = :pid ORDER BY timestamp DESC LIMIT 10"),
        {"pid": part_id}
    ).fetchall()

    result = f"""
    <h3>Отладочная информация для запчасти #{part_id}</h3>
    <p><strong>Название:</strong> {part.part_name}</p>
    <p><strong>Текущий остаток:</strong> {part.quantity_in_stock} шт.</p>
    <p><strong>Минимальный остаток:</strong> {part.min_quantity} шт.</p>

    <h4>Последние 10 операций:</h4>
    <table border="1">
        <tr>
            <th>Время</th>
            <th>Тип</th>
            <th>Количество</th>
            <th>Было</th>
            <th>Стало</th>
            <th>Работа</th>
        </tr>
    """

    for log in logs:
        result += f"""
        <tr>
            <td>{log.timestamp}</td>
            <td>{log.operation_type}</td>
            <td>{log.quantity}</td>
            <td>{log.old_stock}</td>
            <td>{log.new_stock}</td>
            <td>{log.order_comp_id or '-'}</td>
        </tr>
        """

    result += "</table>"
    return result

# Дополнительно: роут для быстрого изменения статуса (без модального окна)
@app.route('/orders/<int:order_id>/status/<string:status>')
@login_required
def quick_update_status(order_id, status):
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)
    valid_statuses = ['принят', 'в работе', 'ожидает запчастей', 'завершен', 'отменен']

    if status not in valid_statuses:
        flash(f'Недопустимый статус: {status}', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    old_status = order.status
    order.status = status

    # Обновляем дату завершения при необходимости
    if status == 'завершен' and not order.completion_date:
        order.completion_date = datetime.now().date()

    db.session.commit()

    flash(f'Статус заказа #{order_id} изменен на "{status}"', 'success')
    return redirect(url_for('order_details', order_id=order_id))


@app.route('/orders/<int:order_id>/invoice')
@login_required
def order_invoice(order_id):
    if current_user.role not in ['admin', 'master', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)

    # Обновляем общую стоимость перед генерацией PDF
    order.update_total()

    # Генерируем PDF с флагом regenerate=True
    pdf_path = generate_order_invoice(order, regenerate=True)

    # Отправляем файл
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f'заказ-наряд_{order_id}.pdf',
        mimetype='application/pdf'
    )


@app.route('/orders/<int:order_id>/delete', methods=['POST'])
@login_required
def delete_order(order_id):
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)

    # Проверяем, можно ли удалять заказ
    # Например, запрещаем удалять завершенные заказы
    if order.status == 'завершен':
        flash('Нельзя удалить завершенный заказ.', 'danger')
        return redirect(url_for('order_details', order_id=order_id))

    try:
        # Получаем все работы (order_composition) для этого заказа
        order_compositions = OrderComposition.query.filter_by(order_id=order_id).all()

        # Собираем все ID работ
        order_comp_ids = [oc.order_comp_id for oc in order_compositions]

        # Удаляем все записи об использовании запчастей для этих работ
        if order_comp_ids:
            from sqlalchemy import text

            # Удаляем записи из inventory_log (если таблица существует)
            try:
                db.session.execute(
                    text("DELETE FROM inventory_log WHERE order_comp_id IN :ids"),
                    {"ids": tuple(order_comp_ids)}
                )
            except:
                pass  # Если таблицы нет, пропускаем

            # Удаляем записи из parts_usage
            PartsUsage.query.filter(PartsUsage.order_comp_id.in_(order_comp_ids)).delete(synchronize_session=False)

        # Удаляем все работы (order_composition) заказа
        OrderComposition.query.filter_by(order_id=order_id).delete(synchronize_session=False)

        # Удаляем сам заказ
        order_number = order.order_id
        db.session.delete(order)
        db.session.commit()

        flash(f'Заказ #{order_number} успешно удален!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении заказа: {str(e)}', 'danger')

    return redirect(url_for('orders_list'))


@app.route('/api/orders/<int:order_id>/update_total', methods=['POST'])
@login_required
def update_order_total(order_id):
    if current_user.role not in ['admin', 'master']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    order = ServiceOrder.query.get_or_404(order_id)

    # Принудительно пересчитываем все работы
    for item in order.order_items:
        # Если у работы нет actual_cost, устанавливаем base_cost из связанной работы
        if item.actual_cost is None and item.work_info:
            item.actual_cost = item.work_info.base_cost

    db.session.commit()

    # Пересчитываем итог
    total = order.update_total()

    return jsonify({
        'success': True,
        'total': f"{total:.2f}",
        'order_id': order_id
    })

# Роуты для склада
@app.route('/warehouse/parts')
@login_required
def parts_list():
    if current_user.role not in ['admin', 'master', 'storekeeper', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    parts = SparePart.query.order_by(SparePart.part_name).all()
    return render_template('warehouse/parts_list.html', parts=parts)


@app.route('/warehouse/parts/add', methods=['POST'])
@login_required
def add_part():
    if current_user.role not in ['admin', 'storekeeper']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        part = SparePart(
            part_name=request.form.get('part_name'),
            part_number=request.form.get('part_number'),
            manufacturer=request.form.get('manufacturer'),
            unit_price=float(request.form.get('unit_price')),
            quantity_in_stock=int(request.form.get('quantity_in_stock', 0)),
            min_quantity=int(request.form.get('min_quantity', 5)),
            location=request.form.get('location')
        )
        db.session.add(part)
        db.session.commit()
        flash('Запчасть успешно добавлена!', 'success')
    except Exception as e:
        flash(f'Ошибка при добавлении запчасти: {str(e)}', 'danger')

    return redirect(url_for('parts_list'))


# Роут для редактирования запчасти
@app.route('/warehouse/parts/<int:part_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_part(part_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('parts_list'))

    part = SparePart.query.get_or_404(part_id)

    if request.method == 'POST':
        try:
            part.part_name = request.form.get('part_name')
            part.part_number = request.form.get('part_number')
            part.manufacturer = request.form.get('manufacturer')
            part.unit_price = float(request.form.get('unit_price'))
            part.min_quantity = int(request.form.get('min_quantity', 5))
            part.location = request.form.get('location')

            db.session.commit()
            flash(f'Запчасть "{part.part_name}" успешно обновлена!', 'success')
            return redirect(url_for('parts_list'))

        except Exception as e:
            flash(f'Ошибка при обновлении запчасти: {str(e)}', 'danger')

    return render_template('warehouse/edit_part.html', part=part)


# Роут для прихода запчастей (увеличение остатка)
@app.route('/warehouse/parts/<int:part_id>/add_stock', methods=['POST'])
@login_required
def add_stock(part_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('parts_list'))

    part = SparePart.query.get_or_404(part_id)

    try:
        quantity = int(request.form.get('quantity', 0))
        if quantity <= 0:
            flash('Количество должно быть положительным числом.', 'danger')
            return redirect(url_for('parts_list'))

        # Увеличиваем количество на складе
        part.quantity_in_stock += quantity

        db.session.commit()
        flash(f'Добавлено {quantity} шт. запчасти "{part.part_name}". Новый остаток: {part.quantity_in_stock}',
              'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении запчасти: {str(e)}', 'danger')

    return redirect(url_for('parts_list'))


# Роут для расхода запчастей (уменьшение остатка)
@app.route('/warehouse/parts/<int:part_id>/use_stock', methods=['POST'])
@login_required
def use_stock(part_id):
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('parts_list'))

    part = SparePart.query.get_or_404(part_id)

    try:
        quantity = int(request.form.get('quantity', 0))
        if quantity <= 0:
            flash('Количество должно быть положительным числом.', 'danger')
            return redirect(url_for('parts_list'))

        # Проверяем, достаточно ли запчастей на складе
        if part.quantity_in_stock < quantity:
            flash(f'Недостаточно запчастей на складе. Доступно: {part.quantity_in_stock}', 'danger')
            return redirect(url_for('parts_list'))

        # Уменьшаем количество на складе
        part.quantity_in_stock -= quantity

        db.session.commit()
        flash(f'Списано {quantity} шт. запчасти "{part.part_name}". Новый остаток: {part.quantity_in_stock}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при списании запчасти: {str(e)}', 'danger')

    return redirect(url_for('parts_list'))

# Роуты для отчётов
@app.route('/reports/orders')
@login_required
def orders_report():
    if current_user.role not in ['admin', 'manager']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status_filter = request.args.get('status', 'завершен')

    # Фильтрация по статусу
    if status_filter == 'completed':
        query = ServiceOrder.query.filter_by(status='завершен')
    elif status_filter == 'in_progress':
        query = ServiceOrder.query.filter_by(status='в работе')
    elif status_filter == 'new':
        query = ServiceOrder.query.filter_by(status='принят')
    else:
        # По умолчанию показываем все заказы
        query = ServiceOrder.query

    # Фильтрация по дате
    if start_date:
        query = query.filter(ServiceOrder.reception_date >= start_date)
    if end_date:
        query = query.filter(ServiceOrder.reception_date <= end_date)

    orders = query.order_by(ServiceOrder.reception_date.desc()).all()

    # Рассчитываем общую выручку
    total_revenue = sum(float(order.total_cost) for order in orders if order.total_cost)

    # Рассчитываем общее количество работ
    total_works = sum(len(order.order_items) for order in orders)

    # Рассчитываем средний чек
    avg_check = total_revenue / len(orders) if orders else 0

    # === ДОБАВЛЯЕМ НОВУЮ ЛОГИКУ ДЛЯ ГРАФИКА ===
    revenue_by_day = {}
    orders_by_day = {}

    # Группируем данные по дням
    for order in orders:
        if order.total_cost and order.reception_date:
            # Преобразуем дату в строку для группировки
            date_str = order.reception_date.strftime('%Y-%m-%d')

            # Суммируем выручку по дням
            revenue_by_day[date_str] = revenue_by_day.get(date_str, 0) + float(order.total_cost)

            # Считаем количество заказов по дням
            orders_by_day[date_str] = orders_by_day.get(date_str, 0) + 1

    # Сортируем дни по возрастанию
    sorted_days = sorted(revenue_by_day.keys())

    # Подготавливаем данные для графика
    chart_labels = []
    chart_revenue = []
    chart_orders = []

    for day in sorted_days:
        chart_labels.append(day)
        chart_revenue.append(revenue_by_day[day])
        chart_orders.append(orders_by_day.get(day, 0))

    return render_template('reports/orders_report.html',
                           orders=orders,
                           total_revenue=total_revenue,
                           total_works=total_works,
                           avg_check=avg_check,
                           start_date=start_date,
                           end_date=end_date,
                           status_filter=status_filter,
                           # Новые данные для графика
                           chart_labels=chart_labels,
                           chart_revenue=chart_revenue,
                           chart_orders=chart_orders)


@app.route('/orders/<int:order_id>/regenerate_invoice', methods=['POST'])
@login_required
def regenerate_invoice(order_id):
    if current_user.role not in ['admin', 'master']:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    order = ServiceOrder.query.get_or_404(order_id)

    try:
        # Обновляем стоимость
        order.update_total()

        # Перегенерируем PDF
        pdf_path = generate_order_invoice(order, regenerate=True)

        flash('PDF отчет успешно обновлен!', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении PDF: {str(e)}', 'danger')

    return redirect(url_for('order_details', order_id=order_id))

@app.route('/recalculate_revenue')
@login_required
def recalculate_revenue():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        # Пересчитываем общую стоимость для всех завершенных заказов
        completed_orders = ServiceOrder.query.filter_by(status='завершен').all()

        for order in completed_orders:
            order.update_total()

        db.session.commit()
        flash(f'Выручка пересчитана для {len(completed_orders)} заказов', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при пересчете выручки: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

# API для получения автомобилей клиента
@app.route('/api/client/<int:client_id>/cars')
@login_required
def get_client_cars(client_id):
    cars = Car.query.filter_by(client_id=client_id).all()
    return jsonify([{
        'car_id': car.car_id,
        'full_name': car.full_name,
        'license_plate': car.license_plate
    } for car in cars])


@app.route('/users')
@login_required
def users_list():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))

    users = User.query.order_by(User.username).all()
    return render_template('users.html', users=users)


# Профиль пользователя
@app.route('/profile')
@login_required
def profile():
    return render_template('profile/view.html', user=current_user)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # Обновление данных профиля
        current_user.full_name = request.form.get('full_name')
        current_user.phone = request.form.get('phone')
        current_user.email = request.form.get('email')
        current_user.bio = request.form.get('bio')

        # Загрузка аватарки
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                # Создаем уникальное имя файла
                filename = secure_filename(
                    f"{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                avatar_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
                os.makedirs(avatar_dir, exist_ok=True)  # Создаем папку если не существует
                filepath = os.path.join(avatar_dir, filename)

                # Сохраняем файл
                file.save(filepath)

                # Создаем миниатюру если установлен Pillow
                if HAS_PIL:
                    create_thumbnail(filepath, (200, 200))

                # Удаляем старую аватарку если она не дефолтная
                if current_user.avatar and current_user.avatar != 'default_avatar.png':
                    old_path = os.path.join(avatar_dir, current_user.avatar)
                    if os.path.exists(old_path):
                        os.remove(old_path)

                current_user.avatar = filename

        db.session.commit()
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile/edit.html', user=current_user)


@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_user.check_password(old_password):
        flash('Неверный текущий пароль.', 'danger')
    elif new_password != confirm_password:
        flash('Новые пароли не совпадают.', 'danger')
    elif len(new_password) < 6:
        flash('Пароль должен содержать минимум 6 символов.', 'danger')
    else:
        current_user.set_password(new_password)
        db.session.commit()
        flash('Пароль успешно изменен!', 'success')

    return redirect(url_for('edit_profile'))


@app.route('/avatar/<filename>')
def serve_avatar(filename):
    avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
    return send_from_directory(avatar_path, filename)

# Обработка ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500




try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Предупреждение: Pillow не установлен. Загрузка изображений будет работать без создания миниатюр.")

def create_thumbnail(image_path, size=(200, 200)):
    """Создание миниатюры изображения"""
    if not HAS_PIL:
        return False

    try:
        img = Image.open(image_path)
        img.thumbnail(size)

        # Сохраняем поверх оригинального файла
        img.save(image_path)
        return True
    except Exception as e:
        print(f"Ошибка при создании миниатюры: {e}")
        return False

if __name__ == '__main__':
    # Инициализация базы данных
    init_db(app)

    app.run(debug=True, port=5000)