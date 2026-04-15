from database.models import db, User, Client, Car, Employee, ServiceWork, SparePart, PartsUsage, OrderComposition, ServiceOrder
# Добавьте недостающие импорты
from config import Config
from werkzeug.security import generate_password_hash


def init_db(app):
    with app.app_context():
        # Создание всех таблиц
        db.create_all()

        # Создание тестовых данных, если таблицы пустые
        if not User.query.first():
            create_test_data()


def create_test_data():
    print("Проверка и создание тестовых данных...")

    # Очистка всех данных (ТОЛЬКО для разработки!)
    print("⚠️  Очистка старых данных...")
    try:
        db.session.query(PartsUsage).delete()
        db.session.query(OrderComposition).delete()
        db.session.query(ServiceOrder).delete()
        db.session.query(Car).delete()
        db.session.query(Client).delete()
        db.session.query(SparePart).delete()
        db.session.query(ServiceWork).delete()
        db.session.query(Employee).delete()
        db.session.query(User).delete()
        db.session.commit()
        print("✓ Старые данные удалены")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  Ошибка при очистке: {e}")

    # 1. Создаем сотрудников
    employees_data = [
        {'last_name': 'Смирнов', 'first_name': 'Алексей', 'position': 'мастер-приёмщик', 'phone': '+79164567890'},
        {'last_name': 'Кузнецов', 'first_name': 'Дмитрий', 'position': 'механик', 'phone': '+79165678901'},
        {'last_name': 'Попов', 'first_name': 'Сергей', 'position': 'механик', 'phone': '+79166789012'},
    ]

    employees = []
    for emp_data in employees_data:
        employee = Employee(**emp_data)
        db.session.add(employee)
        employees.append(employee)
        print(f"✓ Создан сотрудник: {employee.full_name}")

    db.session.commit()

    # 2. Создаем пользователей
    users_data = [
        {'username': 'admin', 'email': 'admin@autoservice.ru', 'password': 'admin123',
         'role': 'admin', 'full_name': 'Администратор Системы', 'employee_id': employees[0].employee_id},
        {'username': 'master', 'email': 'master@autoservice.ru', 'password': 'master123',
         'role': 'master', 'full_name': 'Мастер Иванов', 'employee_id': employees[0].employee_id},
        {'username': 'mechanic1', 'email': 'mechanic1@autoservice.ru', 'password': 'mechanic123',
         'role': 'mechanic', 'full_name': 'Механик Петров', 'employee_id': employees[1].employee_id},
        {'username': 'manager', 'email': 'manager@autoservice.ru', 'password': 'manager123',
         'role': 'manager', 'full_name': 'Руководитель Сидоров'},
    ]

    for user_data in users_data:
        user = User(
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=user_data['role'],
            employee_id=user_data.get('employee_id')
        )
        user.set_password(user_data['password'])
        db.session.add(user)
        print(f"✓ Создан пользователь: {user.username}")

    db.session.commit()

    # 3. Создаем клиентов с УНИКАЛЬНЫМИ телефонами
    clients_data = [
        {'last_name': 'Иванов', 'first_name': 'Сергей', 'phone': '+79161111111', 'email': 'ivanov@mail.ru'},
        {'last_name': 'Петрова', 'first_name': 'Анна', 'phone': '+79162222222', 'email': 'petrova@mail.ru'},
        {'last_name': 'Сидоров', 'first_name': 'Дмитрий', 'phone': '+79163333333', 'email': 'sidorov@mail.ru'},
    ]

    clients = []
    for client_data in clients_data:
        client = Client(**client_data)
        db.session.add(client)
        clients.append(client)
        print(f"✓ Создан клиент: {client.full_name}")

    db.session.commit()

    # 4. Создаем автомобили с УНИКАЛЬНЫМИ VIN и номерами
    import time
    timestamp = int(time.time())

    cars_data = [
        {'client_id': clients[0].client_id, 'brand': 'Toyota', 'model': 'Camry', 'year': 2018,
         'license_plate': f'А{timestamp % 1000}ВС777', 'vin': f'JTDKB20U{timestamp % 100000000}'},
        {'client_id': clients[1].client_id, 'brand': 'BMW', 'model': 'X5', 'year': 2020,
         'license_plate': f'В{(timestamp + 1) % 1000}DE777', 'vin': f'WBAFR710X{timestamp % 1000000}'},
        {'client_id': clients[2].client_id, 'brand': 'Lada', 'model': 'Vesta', 'year': 2021,
         'license_plate': f'С{(timestamp + 2) % 1000}FG777', 'vin': f'XTA210930L{timestamp % 1000000}'},
    ]

    for car_data in cars_data:
        car = Car(**car_data)
        db.session.add(car)
        print(f"✓ Создан автомобиль: {car.brand} {car.model} ({car.license_plate})")

    db.session.commit()

    # 5. Создаем виды работ
    works_data = [
        {'work_name': 'Замена масла', 'description': 'Замена моторного масла и масляного фильтра',
         'standard_hours': 1.0, 'base_cost': 1500.00},
        {'work_name': 'Замена тормозных колодок', 'description': 'Замена передних тормозных колодок',
         'standard_hours': 1.5, 'base_cost': 3000.00},
        {'work_name': 'Диагностика двигателя', 'description': 'Компьютерная диагностика двигателя',
         'standard_hours': 0.5, 'base_cost': 2000.00},
        {'work_name': 'Замена аккумулятора', 'description': 'Замена автомобильного аккумулятора',
         'standard_hours': 0.5, 'base_cost': 1000.00},
    ]

    for work_data in works_data:
        work = ServiceWork(**work_data)
        db.session.add(work)
        print(f"✓ Создана работа: {work.work_name}")

    # 6. Создаем запчасти
    parts_data = [
        {'part_name': 'Моторное масло 5W-30', 'part_number': 'OIL-5W30-5L', 'manufacturer': 'Mobil',
         'unit_price': 3500.00, 'quantity_in_stock': 20, 'min_quantity': 5, 'location': 'Секция А, полка 1'},
        {'part_name': 'Масляный фильтр', 'part_number': 'FILTER-OIL-123', 'manufacturer': 'Mann',
         'unit_price': 800.00, 'quantity_in_stock': 15, 'min_quantity': 5, 'location': 'Секция А, полка 2'},
        {'part_name': 'Тормозные колодки передние', 'part_number': 'PADS-FRONT-456', 'manufacturer': 'Brembo',
         'unit_price': 4500.00, 'quantity_in_stock': 10, 'min_quantity': 4, 'location': 'Секция Б, полка 1'},
        {'part_name': 'Аккумулятор 60Ач', 'part_number': 'BATT-60AH', 'manufacturer': 'VARTA',
         'unit_price': 7000.00, 'quantity_in_stock': 8, 'min_quantity': 2, 'location': 'Секция В, полка 1'},
    ]

    for part_data in parts_data:
        part = SparePart(**part_data)
        db.session.add(part)
        print(f"✓ Создана запчасть: {part.part_name}")

    db.session.commit()

    print("\n" + "=" * 50)
    print("✅ ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!")
    print("=" * 50)
    print("\nТестовые пользователи:")
    print("1. admin / admin123 (Администратор)")
    print("2. master / master123 (Мастер-приёмщик)")
    print("3. mechanic1 / mechanic123 (Механик)")
    print("4. manager / manager123 (Руководитель)")