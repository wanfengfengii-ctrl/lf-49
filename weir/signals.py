from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import GateStatus, HarvestRecord, WaterLevel
from .services.harvest_estimator import recalculate_estimates, estimate_single_day, save_estimate


@receiver(post_save, sender=GateStatus)
def trigger_estimate_recalculation_on_gate_change(sender, instance, **kwargs):
    weir = instance.weir
    start_date = instance.change_time.date()
    end_date = timezone.now().date()
    recalculate_estimates(weir, start_date, end_date)


@receiver(post_delete, sender=GateStatus)
def trigger_estimate_recalculation_on_gate_delete(sender, instance, **kwargs):
    weir = instance.weir
    start_date = instance.change_time.date()
    end_date = timezone.now().date()
    recalculate_estimates(weir, start_date, end_date)


@receiver(post_save, sender=HarvestRecord)
def update_estimate_actual_weight(sender, instance, **kwargs):
    from .models import HarvestEstimate
    estimate, created = HarvestEstimate.objects.get_or_create(
        weir=instance.weir,
        estimate_date=instance.record_date,
        defaults={
            'estimated_weight': 0,
            'has_water_data': False,
            'actual_weight': instance.weight,
        }
    )
    if not created:
        from django.db.models import Sum
        actual = HarvestRecord.objects.filter(
            weir=instance.weir,
            record_date=instance.record_date
        ).aggregate(total=Sum('weight'))['total'] or 0
        estimate.actual_weight = actual
        estimate.save()


@receiver(post_delete, sender=HarvestRecord)
def update_estimate_actual_weight_on_delete(sender, instance, **kwargs):
    from .models import HarvestEstimate
    from django.db.models import Sum

    actual = HarvestRecord.objects.filter(
        weir=instance.weir,
        record_date=instance.record_date
    ).aggregate(total=Sum('weight'))['total'] or 0

    try:
        estimate = HarvestEstimate.objects.get(
            weir=instance.weir,
            estimate_date=instance.record_date
        )
        estimate.actual_weight = actual
        estimate.save()
    except HarvestEstimate.DoesNotExist:
        pass


@receiver(post_save, sender=WaterLevel)
def trigger_estimate_on_water_level(sender, instance, **kwargs):
    if instance.is_primary:
        estimate_data = estimate_single_day(instance.weir, instance.record_date)
        save_estimate(estimate_data)
