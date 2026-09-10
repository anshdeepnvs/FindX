from django.urls import path
from . import views

app_name = 'claims'

urlpatterns = [
    path('match/<int:match_id>/submit/', views.submit_claim, name='submit_claim'),
    path('match/<int:match_id>/ai-chat/send/', views.ai_chat_send, name='ai_chat_send'),
    path('<int:claim_id>/review/', views.review_claim, name='review_claim'),
    path('<int:claim_id>/return/', views.return_confirm, name='return_confirm'),
    path('<int:claim_id>/receipt/', views.receipt_confirm, name='receipt_confirm'),
    path('<int:claim_id>/success/', views.return_success, name='success'),
]
