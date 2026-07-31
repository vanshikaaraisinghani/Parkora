from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Regexp, ValidationError
from models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')

class ParkingLotForm(FlaskForm):
    prime_location_name = StringField('Location Name', 
                                    validators=[DataRequired(), Length(max=200)])
    price = FloatField('Price per Hour (₹)', 
                      validators=[DataRequired(), NumberRange(min=0.01)])
    address = TextAreaField('Address', validators=[DataRequired()])
    pin_code = StringField('PIN Code', 
                          validators=[DataRequired(), Regexp(r'^\d{6}$', message='PIN code must contain exactly 6 digits.')])
    maximum_number_of_spots = IntegerField('Maximum Number of Spots', 
                                         validators=[DataRequired(), NumberRange(min=1, max=500)])
    submit = SubmitField('Submit')
