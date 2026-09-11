from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Item, Category, PrivateDetail
from .forms import ReportItemForm, PrivateDetailForm, ItemSearchForm


def item_list(request):
    form = ItemSearchForm(request.GET)
    items = Item.objects.filter(is_active=True).select_related('reporter', 'category')

    q        = request.GET.get('q', '').strip()
    typ      = request.GET.get('type', '')
    category = request.GET.get('category', '')
    city     = request.GET.get('city', '').strip()

    if q:
        items = items.filter(
            Q(title__icontains=q) | Q(description__icontains=q) |
            Q(brand__icontains=q) | Q(color__icontains=q)
        )
    if typ:
        items = items.filter(item_type=typ)
    if category:
        items = items.filter(category__slug=category)
    if city:
        items = items.filter(city__icontains=city)

    categories = Category.objects.all()
    ctx = {
        'items': items,
        'form': form,
        'categories': categories,
        'total': items.count(),
        'q': q, 'typ': typ, 'selected_city': city,
    }
    return render(request, 'items/list.html', ctx)


def item_detail(request, pk):
    item = get_object_or_404(Item.objects.select_related('reporter', 'category'), pk=pk)
    is_owner = request.user.is_authenticated and request.user == item.reporter

    matches = []
    if is_owner:
        # Guarantee fresh matches for the owner
        if item.is_active and item.status in (Item.STATUS_ACTIVE, Item.STATUS_MATCH_FOUND):
            try:
                from matching.services import run_matching
                run_matching(item)
            except Exception:
                pass

        if item.item_type == 'LOST':
            matches = item.matches_as_lost.filter(final_score__gte=40).order_by('-final_score')[:5]
        else:
            matches = item.matches_as_found.filter(final_score__gte=40).order_by('-final_score')[:5]

    private = None
    if is_owner:
        private = getattr(item, 'private_detail', None)

    is_new = request.GET.get('created') == '1'

    ctx = {
        'item': item,
        'is_owner': is_owner,
        'matches': matches,
        'private': private,
        'is_new': is_new,
    }
    return render(request, 'items/detail.html', ctx)


@login_required
def report_lost(request):
    if request.method == 'POST':
        form    = ReportItemForm(request.POST, request.FILES)
        pvt_form = PrivateDetailForm(request.POST)
        if form.is_valid() and pvt_form.is_valid():
            item = form.save(commit=False)
            item.reporter  = request.user
            item.item_type = Item.TYPE_LOST
            item.save()
            pvt = pvt_form.save(commit=False)
            pvt.item = item
            pvt.save()

            # Synchronously run matching so matches exist immediately on redirect
            match_count = 0
            try:
                from matching.services import run_matching
                match_count = run_matching(item)
            except Exception:
                pass

            if match_count > 0:
                messages.success(request, f'Your lost item report for "{item.title}" has been created. 🎉 FindX detected {match_count} potential match(es)!')
            else:
                messages.success(request, f'Your lost item report for "{item.title}" has been created. FindX will continuously scan for matches!')
            return redirect(f'/items/{item.pk}/?created=1')
    else:
        form     = ReportItemForm()
        pvt_form = PrivateDetailForm()
    return render(request, 'items/report_lost.html', {'form': form, 'pvt_form': pvt_form})


@login_required
def report_found(request):
    if request.method == 'POST':
        form = ReportItemForm(request.POST, request.FILES)
        pvt_form = PrivateDetailForm(request.POST)
        # Hidden info is optional for finders
        pvt_form.fields['hidden_info'].required = False
        if form.is_valid() and pvt_form.is_valid():
            item = form.save(commit=False)
            item.reporter  = request.user
            item.item_type = Item.TYPE_FOUND
            item.save()
            if pvt_form.cleaned_data.get('hidden_info') or pvt_form.cleaned_data.get('challenge_question'):
                pvt = pvt_form.save(commit=False)
                pvt.item = item
                pvt.save()

            # Synchronously run matching so matches exist immediately on redirect
            match_count = 0
            try:
                from matching.services import run_matching
                match_count = run_matching(item)
            except Exception:
                pass

            if match_count > 0:
                messages.success(request, f'Your found item report for "{item.title}" has been posted. 🎉 Found {match_count} matching lost item report(s)!')
            else:
                messages.success(request, f'Your found item report for "{item.title}" has been posted. If we find a matching lost report, we will notify the owner!')
            return redirect(f'/items/{item.pk}/?created=1')
    else:
        form = ReportItemForm()
        pvt_form = PrivateDetailForm()
        pvt_form.fields['hidden_info'].required = False
    return render(request, 'items/report_found.html', {'form': form, 'pvt_form': pvt_form})


@login_required
def item_close(request, pk):
    item = get_object_or_404(Item, pk=pk, reporter=request.user)
    if request.method == 'POST':
        item.is_active = False
        item.status = Item.STATUS_CLOSED
        item.save()
        messages.info(request, f'Item "{item.title}" has been closed.')
        return redirect('core:dashboard')
    return render(request, 'items/confirm_close.html', {'item': item})


def item_matches_status(request, pk):
    """AJAX endpoint that returns current matches for an item to allow real-time UI refresh."""
    item = get_object_or_404(Item, pk=pk)
    if not request.user.is_authenticated or request.user != item.reporter:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        from matching.services import run_matching
        run_matching(item)
    except Exception:
        pass

    if item.item_type == 'LOST':
        matches = item.matches_as_lost.filter(final_score__gte=40).order_by('-final_score')[:5]
    else:
        matches = item.matches_as_found.filter(final_score__gte=40).order_by('-final_score')[:5]

    data = [
        {
            'id': m.id,
            'title': m.found_item.title if item.item_type == 'LOST' else m.lost_item.title,
            'city': m.found_item.city if item.item_type == 'LOST' else m.lost_item.city,
            'score': round(m.final_score),
            'status': m.get_status_display(),
            'review_url': f'/matching/{m.id}/',
        }
        for m in matches
    ]
    return JsonResponse({'count': len(data), 'matches': data})

