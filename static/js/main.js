// Основные JavaScript функции для АСУ Автосервис

$(document).ready(function() {
    // Автоматическое скрытие алертов через 5 секунд
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);

    // Подтверждение удаления
    $('.confirm-delete').on('click', function() {
        return confirm('Вы уверены, что хотите удалить этот элемент?');
    });

    // Динамическая загрузка автомобилей клиента
    $('#client_id').change(function() {
        var clientId = $(this).val();
        if (clientId) {
            $.getJSON('/api/client/' + clientId + '/cars', function(data) {
                var carSelect = $('#car_id');
                carSelect.empty();
                carSelect.append('<option value="">Выберите автомобиль</option>');
                $.each(data, function(index, car) {
                    carSelect.append('<option value="' + car.car_id + '">' +
                        car.full_name + ' (' + car.license_plate + ')</option>');
                });
            });
        }
    });

    // Динамическое добавление строк работ в заказ
    var workCounter = 0;

    $('#add-work-btn').click(function() {
        workCounter++;
        var newRow = `
            <div class="work-row row g-3 mb-3" id="work-row-${workCounter}">
                <div class="col-md-5">
                    <select class="form-select work-select" name="work_ids[]" required>
                        <option value="">Выберите работу</option>
                        {% for work in works %}
                        <option value="{{ work.work_id }}" data-cost="{{ work.base_cost }}">
                            {{ work.work_name }} ({{ work.base_cost }} руб.)
                        </option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <select class="form-select employee-select" name="employee_ids[]">
                        <option value="">Назначить механика</option>
                        {% for employee in employees %}
                        <option value="{{ employee.employee_id }}">
                            {{ employee.full_name }} ({{ employee.position }})
                        </option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="number" class="form-control cost-input"
                           name="costs[]" step="0.01" placeholder="Стоимость" required>
                </div>
                <div class="col-md-1">
                    <button type="button" class="btn btn-danger remove-work-btn"
                            data-row="${workCounter}">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        `;
        $('#works-container').append(newRow);
    });

    // Удаление строки работы
    $(document).on('click', '.remove-work-btn', function() {
        var rowId = $(this).data('row');
        $('#work-row-' + rowId).remove();
        calculateTotal();
    });

    // Автоматическая подстановка стоимости при выборе работы
    $(document).on('change', '.work-select', function() {
        var selectedOption = $(this).find('option:selected');
        var baseCost = selectedOption.data('cost');
        $(this).closest('.work-row').find('.cost-input').val(baseCost);
        calculateTotal();
    });

    // Расчет общей суммы
    function calculateTotal() {
        var total = 0;
        $('.cost-input').each(function() {
            var cost = parseFloat($(this).val()) || 0;
            total += cost;
        });
        $('#total-cost').text(total.toFixed(2) + ' руб.');
        $('#total-cost-input').val(total);
    }

    // Инициализация DataTables для таблиц
    if ($.fn.DataTable) {
        $('.data-table').DataTable({
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/ru.json'
            },
            pageLength: 25,
            responsive: true
        });
    }

    // Обновление времени каждую минуту
    function updateTime() {
        var now = new Date();
        var timeString = now.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        var dateString = now.toLocaleDateString('ru-RU', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        $('#current-time').text(timeString);
        $('#current-date').text(dateString);
    }

    updateTime();
    setInterval(updateTime, 60000);
});