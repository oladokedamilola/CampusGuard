from django.urls import path
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('pricing/', views.PricingView.as_view(), name='pricing'),
    path('contact/', views.ContactView.as_view(), name='contact'),
]