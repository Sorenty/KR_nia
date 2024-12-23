import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import redis
from flask_cors import CORS
from flask_migrate import Migrate
import os

# Создаем логгер
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

app = Flask(__name__)

# Настроить CORS для разрешения доступа только с порта 8080
CORS(app, resources={r"/*": {"origins": "*"}})

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://user:password@db/restaurant_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Подключаем Redis
redis_client = redis.StrictRedis(host='redis', port=6379, decode_responses=True)

db_config = {
    'host': 'restaurant-db',
    'user': 'root',
    'password': 'yourpassword',
    'database': 'restaurant'
}

class Table(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    total_cost = db.Column(db.Float, default=0)
    items = db.relationship('Item', backref='table', lazy=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)

@app.route('/', methods=['GET'])
def home():
    # Отправляем запрос на фронтенд, который работает на порту 8080
    return send_from_directory(os.path.join(app.root_path, 'frontend'), 'index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

@app.route('/tables', methods=['POST'])
def create_table():
    try:
        data = request.json
        if not data:
            logger.error("No JSON data provided in the request.")
            return jsonify({"error": "No JSON data provided."}), 400
        
        table_name = data.get('name')
        
        if not table_name:
            logger.error("Table name is required.")
            return jsonify({"error": "Table name is required."}), 400
        
        # Проверяем, существует ли уже стол с таким именем
        existing_table = Table.query.filter_by(name=table_name).first()
        if existing_table:
            logger.error(f"Table with name '{table_name}' already exists.")  # Логируем с уровнем ошибки
            return jsonify({"error": f"Table with name '{table_name}' already exists."}), 400  # Возвращаем ошибку

        # Создаем новый стол
        new_table = Table(name=table_name)
        db.session.add(new_table)
        db.session.commit()

        logger.info(f"Table '{table_name}' created successfully.")
        return jsonify({"message": f"Table '{table_name}' created successfully.", "table_id": new_table.id}), 201
    except Exception as e:
        logger.exception(f"Error creating table: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500


@app.route('/tables/<int:table_id>/add_items', methods=['POST'])
def add_items(table_id):
    try:
        # Проверяем наличие стола по ID
        table = Table.query.get(table_id)
        if not table:
            logger.error(f"Table {table_id} not found.")
            return jsonify({"error": f"Table {table_id} not found."}), 404

        # Проверяем тело запроса
        data = request.json
        if not data or not isinstance(data, dict):
            logger.error("Invalid JSON format.")
            return jsonify({"error": "Invalid JSON format."}), 400

        # Проверяем наличие списка items
        items = data.get('items')
        if not items or not isinstance(items, list):
            logger.error("'items' must be a list.")
            return jsonify({"error": "'items' must be a list."}), 400

        total_cost = 0
        for item in items:
            dish_name = item.get('name')
            dish_price = item.get('price')
            dish_quantity = item.get('quantity')

            # Проверяем каждое поле
            if not dish_name or not isinstance(dish_price, (int, float)) or not isinstance(dish_quantity, int):
                logger.error(f"Invalid item data: {item}")
                return jsonify({"error": "Each item must have 'name', 'price', and 'quantity'."}), 400

            # Добавляем блюдо
            new_item = Item(name=dish_name, price=dish_price, quantity=dish_quantity, table_id=table_id)
            db.session.add(new_item)
            total_cost += dish_price * dish_quantity

        # Обновляем общую стоимость стола
        try:
            table.total_cost += total_cost
            db.session.commit()
            logger.info(f"Table {table_id} total cost updated: {table.total_cost}")
        except Exception as db_error:
            db.session.rollback()
            logger.exception(f"Database error while updating table {table_id}: {db_error}")
            return jsonify({"error": "Failed to update the database. Please try again."}), 500

        # Кэшируем общую стоимость
        try:
            redis_client.set(f"table:{table_id}:total_cost", table.total_cost)
            logger.info(f"Total cost cached for table {table_id}: {table.total_cost}")
        except Exception as redis_error:
            logger.exception(f"Redis error while caching total cost for table {table_id}: {redis_error}")

        # Используем имя стола вместо его ID в ответе
        return jsonify({"message": f"Success: Items added to table '{table.name}' (ID: {table.id}), Total Cost: {table.total_cost}"}), 200
    except Exception as e:
        logger.exception(f"Unexpected error in add_items: {e}")
        return jsonify({"error": "Internal server error. Please try again later."}), 500



@app.route('/tables/<int:table_id>/total_cost', methods=['GET'])
def get_total_cost(table_id):
    try:
        # Проверяем кэш
        cached_cost = redis_client.get(f"table:{table_id}:total_cost")
        if cached_cost:
            logger.info(f"Returning cached total cost for table {table_id}")
            return jsonify({"table_id": table_id, "total_cost": float(cached_cost), "source": "cache"}), 200

        # Проверяем наличие стола по ID
        table = Table.query.get(table_id)
        if not table:
            logger.error(f"Table {table_id} not found.")
            return jsonify({"error": f"Table {table_id} not found."}), 404

        total_cost = table.total_cost

        try:
            redis_client.set(f"table:{table_id}:total_cost", total_cost)
            logger.info(f"Total cost cached for table {table_id}: {total_cost}")
        except Exception as redis_error:
            logger.exception(f"Redis error while caching total cost for table {table_id}: {redis_error}")

        return jsonify({"table_id": table_id, "total_cost": total_cost, "source": "database"}), 200
    except Exception as e:
        logger.exception(f"Error fetching total cost for table {table_id}: {e}")
        return jsonify({"error": "Failed to retrieve total cost."}), 500


@app.route('/tables', methods=['GET'])
def get_tables():
    try:
        tables = Table.query.all()
        tables_list = [{"id": table.id, "name": table.name, "total_cost": table.total_cost} for table in tables]
        return jsonify(tables_list), 200
    except Exception as e:
        logger.exception(f"Error fetching tables: {e}")
        return jsonify({"error": "An error occurred while fetching tables."}), 500

@app.route('/tables/revenue', methods=['GET'])
def get_total_revenue():
    try:
        total_revenue = redis_client.get("total_revenue")
        if total_revenue:
            logger.info("Returning cached total revenue")
            return jsonify({"total_revenue": float(total_revenue), "source": "cache"}), 200

        total_revenue = db.session.query(db.func.sum(Table.total_cost)).scalar() or 0
        redis_client.set("total_revenue", total_revenue)
        logger.info(f"Total revenue cached: {total_revenue}")
        return jsonify({"total_revenue": total_revenue, "source": "database"}), 200
    except Exception as e:
        logger.exception(f"Error fetching total revenue: {e}")
        return jsonify({"error": "An error occurred while fetching total revenue."}), 500

@app.route('/tables/<int:table_id>/calculate_total_cost', methods=['GET'])
def calculate_total_cost(table_id):
    try:
        # Проверяем наличие стола по ID
        table = Table.query.get(table_id)
        if not table:
            logger.error(f"Table {table_id} not found.")
            return jsonify({"error": f"Table {table_id} not found."}), 404

        # Вычисляем стоимость заказа
        total_order_cost = sum(item.price * item.quantity for item in table.items)
        return jsonify({"table_id": table_id, "total_order_cost": total_order_cost}), 200
    except Exception as e:
        logger.exception(f"Error calculating total cost for table {table_id}: {e}")
        return jsonify({"error": "Failed to calculate total cost."}), 500

@app.route('/clear_all', methods=['POST'])
def clear_all():
    try:
        # Удаляем все записи в таблицах
        db.session.query(Item).delete()
        db.session.flush()  # Обязательно делаем flush перед удалением записи в родительской таблице
        db.session.query(Table).delete()
        db.session.commit()

        # Очистка кэша Redis
        redis_client.flushdb()

        logger.info("All data has been cleared from the database and Redis cache.")
        return jsonify({"message": "All tables and items have been cleared."}), 200
    except Exception as e:
        logger.exception(f"Error clearing the database: {e}")
        db.session.rollback()
        return jsonify({"error": "An error occurred while clearing the database."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
