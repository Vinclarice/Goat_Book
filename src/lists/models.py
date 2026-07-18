from django.db import models

# Create your models here.
class Item(models.Model):
    text = models.TextField(default="")
    list = models.ForeignKey('List', default=None, on_delete=models.CASCADE)

class List(models.Model):
    pass