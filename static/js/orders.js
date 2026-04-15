// AJAX обновление стоимости заказа
function updateOrderTotal(orderId) {
    $.ajax({
        url: '/api/orders/' + orderId + '/update_total',
        method: 'POST',
        success: function(response) {
            if (response.success) {
                $('#totalCost').text(response.total + ' ₽');
                showToast('Стоимость обновлена!', 'success');
            }
        },
        error: function() {
            showToast('Ошибка обновления стоимости', 'danger');
        }
    });
}

// Всплывающие уведомления
function showToast(message, type = 'info') {
    const toast = $(`
        <div class="toast align-items-center text-bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `);

    $('#toastContainer').append(toast);
    const bsToast = new bootstrap.Toast(toast[0]);
    bsToast.show();

    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Автоматическое обновление сумм при изменении работ
$(document).on('change', '.work-select, .part-quantity', function() {
    const orderId = $(this).data('order-id');
    if (orderId) {
        updateOrderTotal(orderId);
    }
});