import random
from datetime import date, timedelta, datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from weir.models import Weir, WaterLevel, GateStatus, HarvestRecord, FishSchool


class Command(BaseCommand):
    help = '生成测试数据'

    def handle(self, *args, **options):
        self.stdout.write('开始生成测试数据...')

        weirs_data = [
            {'code': 'YL-001', 'name': '杨家坝鱼梁', 'location': '沅陵县五强溪镇', 'build_year': 1876, 'gate_count': 5},
            {'code': 'YL-002', 'name': '张家洲鱼梁', 'location': '辰溪县潭湾镇', 'build_year': 1902, 'gate_count': 3},
            {'code': 'YL-003', 'name': '王家河鱼梁', 'location': '溆浦县江口镇', 'build_year': 1935, 'gate_count': 4},
        ]

        weirs = []
        for data in weirs_data:
            weir, created = Weir.objects.get_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'location': data['location'],
                    'build_year': data['build_year'],
                    'gate_count': data['gate_count'],
                    'structure_desc': f'''{data['name']}位于{data['location']}，始建于{data['build_year']}年，
是当地著名的传统鱼梁设施。该鱼梁采用传统竹木结构，
共设有{data['gate_count']}个闸口，根据水位和季节变化灵活调整闸口开合策略，
以达到最佳捕鱼效率。其设计体现了当地先民的治水智慧和对自然规律的深刻理解。'''
                }
            )
            if created:
                self.stdout.write(f'创建鱼梁: {weir.code} - {weir.name}')
            else:
                self.stdout.write(f'鱼梁已存在: {weir.code} - {weir.name}')
            weirs.append(weir)

        weathers = ['晴', '多云', '阴', '小雨', '中雨', '大雨']
        fish_species = ['鲤鱼', '草鱼', '鲢鱼', '鳙鱼', '鲫鱼', '青鱼', '鳜鱼', '鲶鱼']
        fish_types = ['鲤鱼群', '草鱼群', '鲢鱼群', '杂鱼群']

        today = date.today()
        start_date = today - timedelta(days=90)

        for weir in weirs:
            current_date = start_date
            
            for gate_num in range(1, weir.gate_count + 1):
                gate_status = random.choice(['open', 'closed'])
                GateStatus.objects.create(
                    weir=weir,
                    gate_number=f'G-{gate_num}',
                    status=gate_status,
                    change_time=timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                    reason='初始状态设置',
                    operator='系统管理员'
                )

            while current_date <= today:
                if random.random() > 0.1:
                    water_level = round(random.uniform(0.5, 4.5), 2)
                    flow_rate = round(random.uniform(0.2, 3.0), 2)
                    
                    WaterLevel.objects.create(
                        weir=weir,
                        record_date=current_date,
                        water_level=water_level,
                        flow_rate=flow_rate,
                        weather=random.choice(weathers),
                        is_primary=True,
                        notes=f'当日水位{water_level}米，流速{flow_rate}m/s'
                    )

                    if random.random() > 0.3:
                        base_harvest = water_level * 2.5
                        season_factor = 1.0
                        month = current_date.month
                        if month in [3, 4, 5]:
                            season_factor = 1.3
                        elif month in [6, 7, 8]:
                            season_factor = 1.5
                        elif month in [9, 10, 11]:
                            season_factor = 1.1
                        else:
                            season_factor = 0.7

                        species = random.choice(fish_species)
                        weight = round(base_harvest * season_factor * random.uniform(0.7, 1.3), 2)
                        quantity = int(weight * random.uniform(0.5, 1.5))

                        HarvestRecord.objects.create(
                            weir=weir,
                            record_date=current_date,
                            fish_species=species,
                            weight=weight,
                            quantity=max(1, quantity),
                            recorder='研究员' + random.choice(['A', 'B', 'C'])
                        )

                    if random.random() > 0.7:
                        FishSchool.objects.create(
                            weir=weir,
                            record_date=current_date,
                            observe_time=timezone.now().time(),
                            fish_type=random.choice(fish_types),
                            estimated_count=random.randint(10, 200),
                            direction=random.choice(['upstream', 'downstream'])
                        )

                    if random.random() > 0.85:
                        gate_num = f'G-{random.randint(1, weir.gate_count)}'
                        new_status = random.choice(['open', 'closed'])
                        reason = random.choice([
                            '调整捕鱼策略',
                            '水位变化调整',
                            '维护保养',
                            '汛期防护',
                            '渔汛季节调整'
                        ])
                        GateStatus.objects.create(
                            weir=weir,
                            gate_number=gate_num,
                            status=new_status,
                            change_time=timezone.make_aware(datetime.combine(current_date, datetime.min.time())),
                            reason=reason,
                            operator='研究员' + random.choice(['A', 'B', 'C'])
                        )

                current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS('测试数据生成完成！'))
        self.stdout.write(f'共生成 {Weir.objects.count()} 个鱼梁档案')
        self.stdout.write(f'共生成 {WaterLevel.objects.count()} 条水位记录')
        self.stdout.write(f'共生成 {GateStatus.objects.count()} 条闸口状态记录')
        self.stdout.write(f'共生成 {HarvestRecord.objects.count()} 条收获记录')
        self.stdout.write(f'共生成 {FishSchool.objects.count()} 条鱼群记录')
