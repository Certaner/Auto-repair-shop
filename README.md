# Описание
Веб-приложение для управления автосервисом, реализованное на основе микрофреймворка Flask. Для взаимодействия с базой данных PostgreSQL используется ORM SQLAlchemy в связке с расширением Flask-SQLAlchemy, что позволяет объектно-ориентированно работать с таблицами клиентов, автомобилей, заказов и запчастей. Аутентификация и авторизация пользователей организованы через Flask-Login с поддержкой ролевой модели, разграничивающей доступ администраторов, мастеров, механиков и руководителей. Интерфейс построен на HTML5 и CSS3 с применением фреймворка Bootstrap 5 для адаптивного дизайна, а интерактивность обеспечивается JavaScript и библиотекой jQuery для динамической загрузки данных, фильтрации таблиц и валидации форм.

# Файловая структура 
app.py – главный файл Flask-приложения  
config.py – конфигурация приложения  
requirements.txt – указание зависимостей python  
database/ – папка для работы с базой данных  
&emsp;models.py – модели SQLAlchemy  
&emsp;session.py – управление сессиями  
&emsp;db_init.py – инициализация БД  
templates/ – папка с html-шаблонами  
&emsp;base.html – базовый шаблон  
&emsp;admin/users.html - административная панель  
&emsp;profile/ - профиль пользователя  
&emsp;&emsp;view.html - личная страница профиля  
&emsp;&emsp;edit.html - редактирование профиля  
&emsp;auth/ – аутентификация  
&emsp;&emsp;login.html – страница входа  
&emsp;dashboard/ – панель управления  
&emsp;&emsp;index.html – главная страница дашборда  
&emsp;clients/  – клиенты  
&emsp;&emsp;list.html  – список клиентов  
&emsp;&emsp;add.html  – добавление клиента  
&emsp;&emsp;details.html – доп. информация  
&emsp;&emsp;edit.html - редактирование информации  
&emsp;cars/ – автомобили  
&emsp;&emsp;list.html – список автомобилей  
&emsp;&emsp;add.html – добавление автомобиля  
&emsp;employees/ – сотрудники  
&emsp;&emsp;list.html – список сотрудников  
&emsp;&emsp;add.html - добавление сотрудника  
&emsp;&emsp;edit.html - редактирование информации о сотруднике  
&emsp;&emsp;details.html - информация о сотруднике  
&emsp;orders/ – заказы  
&emsp;&emsp;list.html – список заказов  
&emsp;&emsp;add.html – добавление заказа  
&emsp;&emsp;details.html – детали заказа  
&emsp;&emsp;invoice.html – печать заказа  
&emsp;warehouse/ – склад  
&emsp;&emsp;parts_list.html – список запчастей  
&emsp;&emsp;edit_part.html - редактирование информации  
&emsp;reports/  – отчеты  
&emsp;&emsp;orders_report.html  – финансовые отчеты  
&emsp;404.html - страница 404  
static/ – папка со статическими файлами  
&emsp;css/ – стили  
&emsp;js/ – JavaScript  
&emsp;invoices/ – генерируемые PDF (заполняется автоматически)  
&emsp;uploads/avatars - хранение изображений профилей (аватарок)  
utils/ – папка со вспомогательными функциями  
&emsp;pdf_generator.py – генерация PDF-документов  
fonts/ – папка со шрифтами  

# Структура БД
-- Таблица клиентов:
CREATE TABLE client (
    client_id SERIAL PRIMARY KEY,
    last_name VARCHAR(50) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(100),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Таблица автомобилей:
CREATE TABLE car (
    car_id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL,
    brand VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INTEGER,
    license_plate VARCHAR(20) NOT NULL UNIQUE,
    vin VARCHAR(17) UNIQUE,
    FOREIGN KEY (client_id) REFERENCES client(client_id) ON DELETE CASCADE
);
-- Таблица заказ-нарядов
CREATE TABLE service_order (
    order_id SERIAL PRIMARY KEY,
    car_id INTEGER NOT NULL,
    reception_date DATE NOT NULL,
    completion_date DATE,
    status VARCHAR(20) DEFAULT 'принят' CHECK (status IN ('принят', 'в работе', 'ожидает запчастей', 'завершен', 'отменен')),
    total_cost DECIMAL(10, 2) DEFAULT 0.00,
    notes TEXT,
    FOREIGN KEY (car_id) REFERENCES car(car_id) ON DELETE CASCADE
);
-- Таблица видов работ
CREATE TABLE service_work (
    work_id SERIAL PRIMARY KEY,
    work_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    standard_hours DECIMAL(5, 2),
    base_cost DECIMAL(10, 2) NOT NULL
);
-- Таблица сотрудников
CREATE TABLE employee (
    employee_id SERIAL PRIMARY KEY,
    last_name VARCHAR(50) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    position VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    hire_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN DEFAULT TRUE
);
-- Таблица складских деталей
CREATE TABLE spare_part (
    part_id SERIAL PRIMARY KEY,
    part_name VARCHAR(100) NOT NULL,
    part_number VARCHAR(50) UNIQUE,
    manufacturer VARCHAR(100),
    unit_price DECIMAL(10, 2) NOT NULL,
    quantity_in_stock INTEGER DEFAULT 0,
    min_quantity INTEGER DEFAULT 5,
    location VARCHAR(50)
);
-- Таблица состава заказа
CREATE TABLE order_composition (
    order_comp_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    work_id INTEGER NOT NULL,
    employee_id INTEGER,
    actual_hours DECIMAL(5, 2),
    actual_cost DECIMAL(10, 2),
    work_status VARCHAR(20) DEFAULT 'назначена' CHECK (work_status IN ('назначена', 'в работе', 'завершена')),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES service_order(order_id) ON DELETE CASCADE,
    FOREIGN KEY (work_id) REFERENCES service_work(work_id),
    FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
);
-- Таблица использования запчастей
CREATE TABLE parts_usage (
    usage_id SERIAL PRIMARY KEY,
    order_comp_id INTEGER NOT NULL,
    part_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_at_time DECIMAL(10, 2),
    FOREIGN KEY (order_comp_id) REFERENCES order_composition(order_comp_id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES spare_part(part_id)
);
-- Таблица назначения работ
CREATE TABLE work_assignment (
    assignment_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    work_id INTEGER NOT NULL,
    skill_level VARCHAR(20) CHECK (skill_level IN ('начальный', 'средний', 'высокий', 'эксперт')),
    FOREIGN KEY (employee_id) REFERENCES employee(employee_id) ON DELETE CASCADE,
    FOREIGN KEY (work_id) REFERENCES service_work(work_id) ON DELETE CASCADE,
    UNIQUE(employee_id, work_id)
);
