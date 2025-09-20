from datetime import datetime, timedelta
from app import app
from models import db, User, Category, Project, RewardTier, Pledge
import random


def seed_data():
    with app.app_context():
        # reset database
        db.drop_all()
        db.create_all()

        # ---- Users ----
        users = []
        for i in range(1, 11):  # ผู้ใช้ 10 คน
            u = User(username=f"user{i}", password="pass123")
            db.session.add(u)
            users.append(u)

        # ---- Categories ----
        categories = []
        cat_names = ["Technology", "Art", "Education"]
        for c in cat_names:
            cat = Category(name=c)
            db.session.add(cat)
            categories.append(cat)

        db.session.commit()

        # ---- Projects ----
        projects = []
        for i in range(1, 9):  # 8 projects
            p = Project(
                title=f"Project {i}",
                description=f"This is description for project {i}.",
                goal_amount=random.randint(5000, 20000),
                current_amount=0,
                deadline=datetime.utcnow() + timedelta(days=random.randint(5, 30)),
                category=random.choice(categories),
            )
            db.session.add(p)
            projects.append(p)

        db.session.commit()

        # ---- Reward Tiers ----
        for p in projects:
            for r in range(1, 4):  # 2–3 rewards each
                tier = RewardTier(
                    project=p,
                    description=f"Reward {r} for {p.title}",
                    min_amount=100 * r,
                    qty_remaining=random.randint(5, 20),
                )
                db.session.add(tier)

        db.session.commit()

        # ---- Pledges ----
        # ✅ สร้าง pledges สำเร็จ 10 รายการ
        for i in range(10):
            user = random.choice(users)
            project = random.choice(projects)
            reward = random.choice(project.reward_tiers)

            amount = reward.min_amount + random.randint(0, 200)  # มากกว่าขั้นต่ำ
            pledge = Pledge(
                user=user,
                project=project,
                reward_tier=reward,
                amount=amount,
                accepted=True
            )
            project.current_amount += amount
            if reward.qty_remaining is not None and reward.qty_remaining > 0:
                reward.qty_remaining -= 1
            db.session.add(pledge)

        # ❌ สร้าง pledges ถูกปฏิเสธ 10 รายการ
        for i in range(10):
            user = random.choice(users)
            project = random.choice(projects)
            reward = random.choice(project.reward_tiers)

            amount = reward.min_amount - 50  # น้อยกว่าขั้นต่ำเพื่อให้ reject
            pledge = Pledge(
                user=user,
                project=project,
                reward_tier=reward,
                amount=amount,
                accepted=False,
                rejected_reason="Amount below reward minimum"
            )
            db.session.add(pledge)

        db.session.commit()
        print("Database seeded with successful + rejected pledges")


if __name__ == "__main__":
    seed_data()
