from django.urls import path
from . import views

app_name = 'items'

urlpatterns = [
    path('', views.item_list, name='item_list'),
    path('<int:pk>/', views.item_detail, name='item_detail'),
    path('report/lost/', views.report_lost, name='report_lost'),
    path('report/found/', views.report_found, name='report_found'),
    path('<int:pk>/close/', views.item_close, name='item_close'),
    path('<int:pk>/matches-status/', views.item_matches_status, name='item_matches_status'),
]
