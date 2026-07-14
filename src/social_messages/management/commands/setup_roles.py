from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from social_messages.models import IntakeSubmission, IntakeSubmissionAssignment

class Command(BaseCommand):
    help = 'Tạo nhóm Quản trị viên và Chuyên viên cùng với các quyền cơ bản.'

    def handle(self, *args, **options):
        # 1. Tạo hoặc lấy nhóm
        admin_group, created_admin = Group.objects.get_or_create(name='Quản trị viên')
        specialist_group, created_specialist = Group.objects.get_or_create(name='Chuyên viên')
        
        self.stdout.write(self.style.SUCCESS(f'Tạo/Lấy nhóm: Quản trị viên (Mới: {created_admin}), Chuyên viên (Mới: {created_specialist})'))

        # 2. Lấy ContentType cho các model
        submission_ct = ContentType.objects.get_for_model(IntakeSubmission)
        assignment_ct = ContentType.objects.get_for_model(IntakeSubmissionAssignment)

        # Quyền cần thiết cho Admin
        admin_perms = Permission.objects.filter(
            content_type__in=[submission_ct, assignment_ct]
        )
        admin_group.permissions.set(admin_perms)
        
        # Quyền cần thiết cho Chuyên viên (chỉ view và thay đổi submission, có thể view/thay đổi assignment)
        # Chuyên viên không được phép xóa (delete)
        specialist_perms = Permission.objects.filter(
            content_type__in=[submission_ct, assignment_ct],
            codename__in=[
                'view_intakesubmission', 
                'change_intakesubmission',
                'view_intakesubmissionassignment',
                'change_intakesubmissionassignment'
            ]
        )
        specialist_group.permissions.set(specialist_perms)

        self.stdout.write(self.style.SUCCESS('Đã gán quyền thành công.'))
