from flask import Flask 
from flask_wtf import FlaskForm
from wtforms import SearchField,PasswordField,SubmitField,BooleanField
from wtforms.validators import DataRequired,Length,Email,EqualTo


