from decimal import Decimal

from rest_framework import serializers

from payment_methods.serializers import MethodAllocationInputSerializer

from .models import Employee, FactoryOverheadSetting, Machine, ManufacturingCostsStats, PayableEntity, Payment


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class EmployeeReadSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Employee
        fields = [
            "id", "name", "monthly_salary", "avg_hours_per_day", "working_days_per_month",
            "rate_per_hour", "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields


class EmployeeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Employee
        fields = ["name", "monthly_salary", "avg_hours_per_day", "working_days_per_month"]

    def validate_monthly_salary(self, value):
        if value <= 0:
            raise serializers.ValidationError("Monthly salary must be greater than zero.")
        return value

    def validate_avg_hours_per_day(self, value):
        if value <= 0:
            raise serializers.ValidationError("Average hours per day must be greater than zero.")
        return value

    def validate_working_days_per_month(self, value):
        if value <= 0:
            raise serializers.ValidationError("Working days per month must be greater than zero.")
        return value


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------

class MachineReadSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Machine
        fields = [
            "id", "name", "category", "avg_hours_per_day", "working_days_per_month",
            "monthly_repair_cost", "rate_per_hour", "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields


class MachineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Machine
        fields = ["name", "category", "avg_hours_per_day", "working_days_per_month", "monthly_repair_cost"]

    def validate_avg_hours_per_day(self, value):
        if value <= 0:
            raise serializers.ValidationError("Average hours per day must be greater than zero.")
        return value

    def validate_working_days_per_month(self, value):
        if value <= 0:
            raise serializers.ValidationError("Working days per month must be greater than zero.")
        return value

    def validate_monthly_repair_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Monthly repair cost cannot be negative.")
        return value


class FactoryOverheadSettingSerializer(serializers.ModelSerializer):
    updated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = FactoryOverheadSetting
        fields = ["rent_amount", "electricity_amount", "updated_by", "updated_at"]
        read_only_fields = ["updated_by", "updated_at"]

    def validate_rent_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Rent cannot be negative.")
        return value

    def validate_electricity_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Electricity cannot be negative.")
        return value


# ---------------------------------------------------------------------------
# PayableEntity (Page 4)
# ---------------------------------------------------------------------------

class PayableEntityReadSerializer(serializers.ModelSerializer):
    name           = serializers.CharField(read_only=True)
    employee       = EmployeeReadSerializer(read_only=True)
    machine        = MachineReadSerializer(read_only=True)
    can_be_deleted = serializers.SerializerMethodField()

    class Meta:
        model  = PayableEntity
        fields = [
            "id", "type", "name", "employee", "machine",
            "overall_total_paid", "overall_payment_count", "can_be_deleted", "created_at",
        ]
        read_only_fields = fields

    def get_can_be_deleted(self, obj):
        if obj.type == PayableEntity.Type.EMPLOYEE:
            return bool(obj.employee and obj.employee.is_deleted)
        if obj.type == PayableEntity.Type.MACHINE:
            return bool(obj.machine and obj.machine.is_deleted)
        return False


class PayableEntityStatsSerializer(serializers.Serializer):
    overall_average_monthly = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    last_month_expense      = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    avg_last_3_months       = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)


# ---------------------------------------------------------------------------
# Payment (Page 4 detail / Page 5)
# ---------------------------------------------------------------------------

class PaymentReadSerializer(serializers.ModelSerializer):
    entity_name = serializers.CharField(source="entity.name", read_only=True)
    entity_type = serializers.CharField(source="entity.type", read_only=True)
    created_by  = serializers.StringRelatedField(read_only=True)
    allocations = serializers.SerializerMethodField()

    class Meta:
        model  = Payment
        fields = [
            "id", "reference_number", "entity", "entity_name", "entity_type",
            "amount", "payment_date", "note", "allocations",
            "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_allocations(self, obj):
        from payment_methods.serializers import PaymentAllocationReadSerializer

        prefetched = self.context.get("manufacturing_costs_payment_allocations")
        if prefetched is not None:
            rows = prefetched.get(obj.id, [])
        else:
            from payment_methods.selectors import get_allocations_for_source
            rows = get_allocations_for_source(obj)
        return PaymentAllocationReadSerializer(rows, many=True).data


class PaymentWriteSerializer(serializers.Serializer):
    entity_id          = serializers.IntegerField()
    amount             = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    payment_date       = serializers.DateField()
    note               = serializers.CharField(required=False, allow_blank=True, default="")
    method_allocations = MethodAllocationInputSerializer(many=True)

    def validate_method_allocations(self, value):
        if not value:
            raise serializers.ValidationError("At least one method must be selected.")
        return value


# ---------------------------------------------------------------------------
# Overview page stats — Page 1
# ---------------------------------------------------------------------------

class ManufacturingCostsStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ManufacturingCostsStats
        fields = [
            "total_employees", "total_machines",
            "total_estimated_monthly_dl", "total_estimated_monthly_foh",
            "last_month_dl_paid", "last_month_foh_paid",
            "this_month_dl_paid", "this_month_foh_paid",
            "last_updated_at",
        ]
        read_only_fields = fields
