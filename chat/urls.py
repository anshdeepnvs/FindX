from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.conversation_list, name='conversation_list'),
    path('<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('<int:pk>/send/', views.send_message, name='send_message'),
    path('<int:pk>/confirm-owner/', views.finder_confirm_owner, name='confirm_owner'),
    path('<int:pk>/decline-claim/', views.finder_decline_claim, name='decline_claim'),
    path('<int:pk>/poll/', views.poll_messages, name='poll_messages'),
]
