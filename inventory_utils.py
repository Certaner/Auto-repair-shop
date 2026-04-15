from database.models import db, SparePart, PartsUsage
from sqlalchemy import text
from flask import request
from flask_login import current_user

class InventoryManager:
    """Управление инвентарем с защитой от дублирования"""

    @staticmethod
    def use_part(order_comp_id, part_id, quantity, unit_price_at_time):
        """
        Использовать запчасть с гарантией однократного вычитания
        Возвращает (успех, сообщение)
        """
        try:
            # Читаем запчасть с блокировкой строки для защиты от race conditions
            part = SparePart.query.filter_by(part_id=part_id).with_for_update().first()
            if not part:
                return False, "Запчасть не найдена"

            current_stock = part.quantity_in_stock

            # Проверяем наличие
            if current_stock < quantity:
                return False, f"Недостаточно на складе. Доступно: {current_stock}"

            # Создаем запись использования
            usage = PartsUsage(
                order_comp_id=order_comp_id,
                part_id=part_id,
                quantity=quantity,
                unit_price_at_time=unit_price_at_time
            )
            db.session.add(usage)

            # Атомарный SQL UPDATE для гарантии однократного вычитания
            result = db.session.execute(
                text("""
                    UPDATE spare_part 
                    SET quantity_in_stock = quantity_in_stock - :qty 
                    WHERE part_id = :pid 
                    AND quantity_in_stock >= :qty
                    RETURNING quantity_in_stock
                """),
                {"qty": quantity, "pid": part_id}
            )

            updated_row = result.fetchone()
            if not updated_row:
                db.session.rollback()
                return False, "Ошибка при обновлении остатков"

            # Коммитим ВСЕ изменения
            db.session.commit()

            new_stock = updated_row[0]
            print(f"✅ Использовано {quantity} шт. запчасти {part_id}. Новый остаток: {new_stock}")

            # Логируем (теперь с current_user и request)
            log_inventory_operation(
                part_id=part_id,
                order_comp_id=order_comp_id,
                quantity=quantity,
                old_stock=current_stock,
                new_stock=new_stock,
                operation_type='USE',
                user_id=current_user.id if current_user.is_authenticated else None,
                ip_address=request.remote_addr
            )

            return True, f"Запчасть использована. Остаток: {new_stock}"

        except Exception as e:
            db.session.rollback()
            print(f"❌ Ошибка в InventoryManager: {str(e)}")
            return False, f"Системная ошибка: {str(e)}"

def log_inventory_operation(part_id, order_comp_id, quantity, old_stock, new_stock,
                          operation_type='USE', user_id=None, ip_address=None):
    """Логируем все операции с инвентарем"""
    try:
        db.session.execute(
            text("""
                INSERT INTO inventory_log 
                (part_id, order_comp_id, quantity, old_stock, new_stock, 
                 operation_type, user_id, ip_address)
                VALUES (:part_id, :order_comp_id, :quantity, :old_stock, :new_stock,
                        :operation_type, :user_id, :ip_address)
            """),
            {
                "part_id": part_id,
                "order_comp_id": order_comp_id,
                "quantity": quantity,
                "old_stock": old_stock,
                "new_stock": new_stock,
                "operation_type": operation_type,
                "user_id": user_id,
                "ip_address": ip_address
            }
        )
        db.session.commit()
    except Exception as e:
        print(f"Ошибка логгирования: {e}")
        db.session.rollback()