// AJAX для завершения работ
function completeWork(orderId, workId) {
    if (!confirm('Отметить работу как выполненную?')) {
        return;
    }

    $.ajax({
        url: `/orders/${orderId}/complete_work/${workId}`,
        method: 'POST',
        success: function(response) {
            // Перезагружаем страницу для обновления данных
            location.reload();
        },
        error: function(xhr) {
            alert('Ошибка при обновлении статуса работы');
        }
    });
}

// Отслеживание кликов по кнопкам завершения
$(document).ready(function() {
    $('.complete-work-btn').click(function(e) {
        e.preventDefault();
        var orderId = $(this).data('order-id');
        var workId = $(this).data('work-id');
        completeWork(orderId, workId);
    });
});