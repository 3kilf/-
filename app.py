from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SelectField, DateField, FloatField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from datetime import datetime, date
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-39')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'


@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)


# ==================== ФОРМЫ WTForms ====================

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Войти')


class RawMaterialForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(max=100)])
    quantity_pieces = IntegerField('Кол-во штук', validators=[NumberRange(min=0)])
    quantity_units = StringField('Кол-во единиц', validators=[Length(max=50)])
    arrival_date = DateField('Дата привоза', format='%Y-%m-%d')
    location = StringField('Место на складе', validators=[Length(max=100)])
    submit = SubmitField('Добавить')


class FinishedProductForm(FlaskForm):
    aroma_name = StringField('Название аромата', validators=[DataRequired(), Length(max=100)])
    shelf = StringField('Полка', validators=[Length(max=50)])
    drawer = StringField('Тумба', validators=[Length(max=50)])
    warehouse = StringField('Склад', validators=[Length(max=100)])
    submit = SubmitField('Добавить')


class AromaForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(max=100)])
    in_work = IntegerField('В работе', validators=[NumberRange(min=0)])
    warehouse = IntegerField('Склад', validators=[NumberRange(min=0)])
    submit = SubmitField('Добавить')


class ClientOrderForm(FlaskForm):
    client_name = StringField('Клиент', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Телефон', validators=[Optional(), Length(max=20)])
    order_date = DateField('Дата заказа', validators=[DataRequired()], format='%Y-%m-%d')
    product_type = StringField('Вид продукции', validators=[Optional(), Length(max=100)])
    aroma = StringField('Аромат', validators=[Optional(), Length(max=100)])
    status = SelectField('Статус', choices=[
        ('В работе', 'В работе'),
        ('Готов', 'Готов'),
        ('Ожидает', 'Ожидает')
    ])
    submit = SubmitField('Добавить')


# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='employee')
    full_name = db.Column(db.String(100))

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_chief(self):
        return self.role == 'chief'


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(50))
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))


# Модель товара склада с категориями
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # духи, свечи, румы, сырье, ароматы

    # Поля для сырья
    quantity_pieces = db.Column(db.Integer, default=0)
    quantity_units = db.Column(db.String(50))
    arrival_date = db.Column(db.Date)
    location = db.Column(db.String(100))

    # Поля для готовой продукции (духи, свечи, румы)
    aroma_name = db.Column(db.String(100))
    shelf = db.Column(db.String(50))
    drawer = db.Column(db.String(50))
    warehouse = db.Column(db.String(100))

    # Поля для ароматов
    in_work = db.Column(db.Integer, default=0)


class ClientOrder(db.Model):
    __tablename__ = 'client_orders'
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    order_date = db.Column(db.Date, nullable=False)
    product_type = db.Column(db.String(100))
    aroma = db.Column(db.String(100))
    status = db.Column(db.String(50), default='В работе')


# Модель рецепта (смеси)
class Recipe(db.Model):
    __tablename__ = 'recipes'
    id = db.Column(db.Integer, primary_key=True)
    product_type = db.Column(db.String(100), nullable=False)  # рум спрей, диффузор и т.д.
    total_weight = db.Column(db.Float, default=100.0)  # масса на 1 единицу в граммах
    ingredients = db.relationship('RecipeIngredient', backref='recipe', lazy=True, cascade='all, delete-orphan')


class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredients'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    ingredient_name = db.Column(db.String(100), nullable=False)
    amount_grams = db.Column(db.Float, nullable=False)
    percentage = db.Column(db.Float, nullable=False)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def check_time_conflict(date_str, start_time, end_time, new_event_type, exclude_id=None):
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return False

    events = Event.query.filter_by(date=target_date).all()
    restricted_types = {'rental', 'masterclass'}

    for ev in events:
        if exclude_id and ev.id == exclude_id:
            continue
        if start_time < ev.end_time and end_time > ev.start_time:
            if new_event_type in restricted_types and ev.event_type in restricted_types:
                return False
    return True


# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================

with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        chief = User(username='chief', role='chief', full_name='Начальник')
        chief.set_password('chief123')
        employee = User(username='employee', role='employee', full_name='Сотрудник')
        employee.set_password('emp123')
        db.session.add_all([chief, employee])

        # Тестовые товары склада
        db.session.add_all([
            # Сырье
            Product(name='Воск соевый', category='сырье', quantity_pieces=50, quantity_units='кг',
                    arrival_date=datetime.strptime('01.06.2026', '%d.%m.%Y').date(), location='Полка 1'),
            Product(name='Воск оливковый', category='сырье', quantity_pieces=30, quantity_units='кг',
                    arrival_date=datetime.strptime('01.06.2026', '%d.%m.%Y').date(), location='Полка 1'),
            Product(name='Аромамасло Лаванда', category='сырье', quantity_pieces=20, quantity_units='л',
                    arrival_date=datetime.strptime('05.06.2026', '%d.%m.%Y').date(), location='Полка 2'),
            Product(name='Масло ши', category='сырье', quantity_pieces=15, quantity_units='кг',
                    arrival_date=datetime.strptime('01.06.2026', '%d.%m.%Y').date(), location='Полка 3'),
            Product(name='Масло миндаля', category='сырье', quantity_pieces=15, quantity_units='л',
                    arrival_date=datetime.strptime('01.06.2026', '%d.%m.%Y').date(), location='Полка 3'),
            Product(name='Парфюмерная база', category='сырье', quantity_pieces=40, quantity_units='л',
                    arrival_date=datetime.strptime('03.06.2026', '%d.%m.%Y').date(), location='Полка 2'),
            Product(name='База ММБ', category='сырье', quantity_pieces=35, quantity_units='л',
                    arrival_date=datetime.strptime('03.06.2026', '%d.%m.%Y').date(), location='Полка 2'),

            # Духи
            Product(name='Твердые духи', category='духи', aroma_name='Лаванда',
                    shelf='Полка 1', drawer='Тумба 1', warehouse='Основной'),
            Product(name='Твердые духи', category='духи', aroma_name='Роза',
                    shelf='Полка 1', drawer='Тумба 1', warehouse='Основной'),

            # Свечи
            Product(name='Свеча контейнерная', category='свечи', aroma_name='Ваниль',
                    shelf='Полка 2', drawer='Тумба 2', warehouse='Основной'),
            Product(name='Свеча интерьерная', category='свечи', aroma_name='Лаванда',
                    shelf='Полка 2', drawer='Тумба 2', warehouse='Основной'),

            # Румы
            Product(name='Рум спрей', category='румы', aroma_name='Жасмин',
                    shelf='Полка 3', drawer='Тумба 3', warehouse='Основной'),
            Product(name='Диффузор', category='румы', aroma_name='Лаванда',
                    shelf='Полка 3', drawer='Тумба 3', warehouse='Основной'),
            Product(name='Авто диффузер', category='румы', aroma_name='Ваниль',
                    shelf='Полка 3', drawer='Тумба 4', warehouse='Основной'),

            # Ароматы
            Product(name='Лаванда', category='ароматы', in_work=10, warehouse=50),
            Product(name='Ваниль', category='ароматы', in_work=5, warehouse=30),
            Product(name='Роза', category='ароматы', in_work=8, warehouse=25),
            Product(name='Жасмин', category='ароматы', in_work=3, warehouse=20),
        ])

        # Рецепты (смеси)
        recipes_data = [
            {
                'product_type': 'Аромасаше',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'Воск оливковый', 'grams': 90.0, 'percentage': 90.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
            {
                'product_type': 'Свеча контейнерная',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'Воск соевый', 'grams': 90.0, 'percentage': 90.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
            {
                'product_type': 'Свеча интерьерная',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'Воск соевый', 'grams': 90.0, 'percentage': 90.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
            {
                'product_type': 'Рум спрей',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'Парфюмерная база', 'grams': 90.0, 'percentage': 90.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
            {
                'product_type': 'Диффузор',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'База ММБ', 'grams': 90.0, 'percentage': 90.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
            {
                'product_type': 'Авто диффузер',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'База ММБ', 'grams': 90.0, 'percentage': 90.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
            {
                'product_type': 'Твердые духи',
                'total_weight': 100.0,
                'ingredients': [
                    {'name': 'Соевый воск', 'grams': 40.0, 'percentage': 40.0},
                    {'name': 'Масло ши', 'grams': 25.0, 'percentage': 25.0},
                    {'name': 'Масло миндаля', 'grams': 25.0, 'percentage': 25.0},
                    {'name': 'Аромамасло', 'grams': 10.0, 'percentage': 10.0},
                ]
            },
        ]

        for recipe_data in recipes_data:
            recipe = Recipe(
                product_type=recipe_data['product_type'],
                total_weight=recipe_data['total_weight']
            )
            db.session.add(recipe)
            db.session.flush()
            for ing in recipe_data['ingredients']:
                ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_name=ing['name'],
                    amount_grams=ing['grams'],
                    percentage=ing['percentage']
                )
                db.session.add(ingredient)

        # Тестовые заказы клиентов
        db.session.add_all([
            ClientOrder(client_name='ООО АромаМир', phone='+79001112233',
                        order_date=datetime.strptime('08.06.2026', '%d.%m.%Y').date(),
                        product_type='Свечи интерьерные', aroma='Лаванда, Ваниль', status='Готов'),
            ClientOrder(client_name='ООО АромаМир', phone='+79001112233',
                        order_date=datetime.strptime('15.06.2026', '%d.%m.%Y').date(),
                        product_type='Свечи интерьерные', aroma='Лаванда, Ваниль', status='В работе'),
            ClientOrder(client_name='ИП Петрова', phone='+79165554433',
                        order_date=datetime.strptime('08.06.2026', '%d.%m.%Y').date(),
                        product_type='Ароматические саше', aroma='Роза, Жасмин', status='Готов'),
            ClientOrder(client_name='ИП Петрова', phone='+79165554433',
                        order_date=datetime.strptime('02.06.2026', '%d.%m.%Y').date(),
                        product_type='Ароматические саше', aroma='Роза, Жасмин', status='В работе'),
        ])

        db.session.commit()
        print("База создана. chief/chief123 или employee/emp123")


# ==================== ОСНОВНЫЕ МАРШРУТЫ ====================

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('calendar'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Добро пожаловать, ' + user.full_name + '!', 'success')
            return redirect(url_for('calendar'))
        flash('Неверный логин или пароль', 'error')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ==================== КАЛЕНДАРЬ ====================

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')


@app.route('/api/events', methods=['GET'])
@login_required
def get_events():
    events = Event.query.all()
    events_list = []
    colors = {
        'work_shift': '#3498db',
        'rental': '#f1c40f',
        'masterclass': '#2ecc71'
    }
    for event in events:
        is_chief = current_user.is_chief()
        is_owner = (event.user_id == current_user.id)
        is_shift = (event.event_type == 'work_shift')
        can_edit = is_chief or (is_owner and is_shift)
        events_list.append({
            'id': event.id,
            'title': event.title,
            'start': f"{event.date}T{event.start_time}",
            'end': f"{event.date}T{event.end_time}",
            'type': event.event_type,
            'editable': can_edit,
            'backgroundColor': colors.get(event.event_type, '#95a5a6')
        })
    return jsonify(events_list)


@app.route('/api/events', methods=['POST'])
@login_required
def create_event():
    data = request.get_json()
    if not all([data.get('title'), data.get('type'), data.get('date'), data.get('start'), data.get('end')]):
        return jsonify({'error': 'Заполните все поля'}), 400
    if data['end'] <= data['start']:
        return jsonify({'error': 'Время окончания должно быть позже начала'}), 400
    if not current_user.is_chief() and data['type'] != 'work_shift':
        return jsonify({'error': 'У вас нет прав создавать это событие'}), 403
    if not check_time_conflict(data['date'], data['start'], data['end'], data['type']):
        return jsonify({'error': 'Конфликт времени!'}), 400
    event = Event(
        title=data['title'], event_type=data['type'],
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        start_time=data['start'], end_time=data['end'],
        user_id=current_user.id
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({'success': True, 'id': event.id})


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    is_chief = current_user.is_chief()
    is_owner = (event.user_id == current_user.id)
    is_shift = (event.event_type == 'work_shift')
    if not (is_chief or (is_owner and is_shift)):
        return jsonify({'error': 'Нет прав на удаление'}), 403
    db.session.delete(event)
    db.session.commit()
    return jsonify({'success': True})


# ==================== СКЛАД (с аккордеоном по категориям) ====================

@app.route('/warehouse')
@login_required
def warehouse():
    products = Product.query.all()
    grouped = {
        'сырье': [p for p in products if p.category == 'сырье'],
        'духи': [p for p in products if p.category == 'духи'],
        'свечи': [p for p in products if p.category == 'свечи'],
        'румы': [p for p in products if p.category == 'румы'],
        'ароматы': [p for p in products if p.category == 'ароматы'],
    }
    return render_template('warehouse.html', grouped=grouped)


@app.route('/warehouse/add/<category>', methods=['GET', 'POST'])
@login_required
def add_product(category):
    if category == 'сырье':
        form = RawMaterialForm()
    elif category in ['духи', 'свечи', 'румы']:
        form = FinishedProductForm()
    elif category == 'ароматы':
        form = AromaForm()
    else:
        flash('Неизвестная категория', 'error')
        return redirect(url_for('warehouse'))

    if form.validate_on_submit():
        product = Product(category=category)
        if category == 'сырье':
            product.name = form.name.data
            product.quantity_pieces = form.quantity_pieces.data
            product.quantity_units = form.quantity_units.data
            product.arrival_date = form.arrival_date.data
            product.location = form.location.data
        elif category in ['духи', 'свечи', 'румы']:
            product.name = category.capitalize()
            product.aroma_name = form.aroma_name.data
            product.shelf = form.shelf.data
            product.drawer = form.drawer.data
            product.warehouse = form.warehouse.data
        elif category == 'ароматы':
            product.name = form.name.data
            product.in_work = form.in_work.data
            product.warehouse = str(form.warehouse.data)
        db.session.add(product)
        db.session.commit()
        flash('Товар добавлен', 'success')
        return redirect(url_for('warehouse'))

    return render_template('warehouse_add.html', form=form, category=category)


@app.route('/warehouse/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    if not current_user.is_chief():
        flash('Нет прав для удаления', 'error')
        return redirect(url_for('warehouse'))
    db.session.delete(Product.query.get_or_404(product_id))
    db.session.commit()
    flash('Товар удален', 'success')
    return redirect(url_for('warehouse'))


# ==================== ПРОИЗВОДСТВО ====================

@app.route('/production')
@login_required
def production():
    items = ClientOrder.query.order_by(ClientOrder.order_date.asc()).all()
    for index, item in enumerate(items, start=1):
        item.priority = index
    return render_template('production.html', items=items)


@app.route('/production/update/<int:order_id>', methods=['POST'])
@login_required
def update_production_status(order_id):
    order = ClientOrder.query.get_or_404(order_id)
    order.status = request.form.get('status', order.status)
    db.session.commit()
    flash('Статус обновлен', 'success')
    return redirect(url_for('production'))


# ==================== КЛИЕНТЫ И ЗАКАЗЫ ====================

@app.route('/clients', methods=['GET', 'POST'])
@login_required
def clients():
    form = ClientOrderForm()
    if form.validate_on_submit():
        new_order = ClientOrder(
            client_name=form.client_name.data,
            phone=form.phone.data,
            order_date=form.order_date.data,
            product_type=form.product_type.data,
            aroma=form.aroma.data,
            status=form.status.data
        )
        db.session.add(new_order)
        db.session.commit()
        flash('Заказ добавлен', 'success')
        return redirect(url_for('clients'))

    orders = ClientOrder.query.order_by(ClientOrder.client_name, ClientOrder.order_date.desc()).all()
    clients_dict = {}
    for order in orders:
        if order.client_name not in clients_dict:
            clients_dict[order.client_name] = {'phone': order.phone, 'orders': []}
        clients_dict[order.client_name]['orders'].append(order)

    return render_template('clients.html', clients=clients_dict, form=form)


@app.route('/clients/edit/<int:order_id>', methods=['POST'])
@login_required
def edit_order(order_id):
    order = ClientOrder.query.get_or_404(order_id)
    order.status = request.form.get('status', order.status)
    db.session.commit()
    flash('Статус обновлен', 'success')
    return redirect(url_for('clients'))


@app.route('/clients/delete/<int:order_id>')
@login_required
def delete_order(order_id):
    if not current_user.is_chief():
        flash('Нет прав для удаления', 'error')
        return redirect(url_for('clients'))
    order = ClientOrder.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    flash('Заказ удален', 'success')
    return redirect(url_for('clients'))


# ==================== РЕЦЕПТЫ (СМЕСИ) ====================

@app.route('/recipes')
@login_required
def recipes():
    recipes = Recipe.query.all()
    return render_template('recipes.html', recipes=recipes)


@app.route('/recipes/add', methods=['GET', 'POST'])
@login_required
def add_recipe():
    if not current_user.is_chief():
        flash('Нет прав для добавления рецепта', 'error')
        return redirect(url_for('recipes'))

    if request.method == 'POST':
        product_type = request.form.get('product_type')
        total_weight = float(request.form.get('total_weight', 100))

        recipe = Recipe(product_type=product_type, total_weight=total_weight)
        db.session.add(recipe)
        db.session.flush()

        ingredient_names = request.form.getlist('ingredient_name[]')
        ingredient_grams = request.form.getlist('ingredient_grams[]')
        ingredient_percents = request.form.getlist('ingredient_percent[]')

        for name, grams, percent in zip(ingredient_names, ingredient_grams, ingredient_percents):
            if name:
                ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_name=name,
                    amount_grams=float(grams),
                    percentage=float(percent)
                )
                db.session.add(ingredient)

        db.session.commit()
        flash('Рецепт добавлен', 'success')
        return redirect(url_for('recipes'))

    return render_template('recipes_add.html')


@app.route('/recipes/delete/<int:recipe_id>')
@login_required
def delete_recipe(recipe_id):
    if not current_user.is_chief():
        flash('Нет прав для удаления', 'error')
        return redirect(url_for('recipes'))
    recipe = Recipe.query.get_or_404(recipe_id)
    db.session.delete(recipe)
    db.session.commit()
    flash('Рецепт удален', 'success')
    return redirect(url_for('recipes'))


if __name__ == '__main__':
    app.run(debug=True)