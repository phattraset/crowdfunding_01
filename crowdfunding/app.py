from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from models import db, User, Project, RewardTier, Category, Pledge
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crowdfunding.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'secretkey'

db.init_app(app)

# ---------------- Helper ----------------
def current_user():
    uid = session.get('user_id')
    if uid:
        return User.query.get(uid)
    return None

# ---------------- Leaderboard: quotas + minimums ----------------
GOLD_MIN = 1000
SILVER_MIN = 300
BRONZE_MIN = 100

GOLD_QUOTA = 3
SILVER_QUOTA = 10

def get_leaderboard(project_id):
    # รวมยอดบริจาคต่อผู้ใช้ (เฉพาะ accepted) และเรียงจากมากไปน้อย
    rows = (
        db.session.query(
            User.username,
            func.sum(Pledge.amount).label('total')
        )
        .join(Pledge.user)
        .filter(Pledge.project_id == project_id, Pledge.accepted == True)
        .group_by(User.id)
        .order_by(func.sum(Pledge.amount).desc())
        .all()
    )

    leaderboard = []
    gold_count = 0
    silver_count = 0

    for idx, row in enumerate(rows, start=1):
        total = int(row.total or 0)

        if total >= GOLD_MIN and gold_count < GOLD_QUOTA:
            tier = "Gold"
            gold_count += 1
        elif total >= SILVER_MIN and silver_count < SILVER_QUOTA:
            tier = "Silver"
            silver_count += 1
        elif total >= BRONZE_MIN:
            tier = "Bronze"
        else:
            tier = "None"

        leaderboard.append({
            "rank": idx,
            "username": row.username,
            "total": total,
            "tier": tier
        })

    return leaderboard

# ---------------- Reward progress (per user per project) ----------------
def user_total_for_project(user_id: int, project_id: str) -> int:
    if not user_id:
        return 0
    total = (
        db.session.query(func.coalesce(func.sum(Pledge.amount), 0))
        .filter(
            Pledge.user_id == user_id,
            Pledge.project_id == project_id,
            Pledge.accepted == True
        )
        .scalar()
    )
    return int(total or 0)

def reward_progress_for_user(project_id: str, user_id: int):
    tiers = (RewardTier.query
             .filter_by(project_id=project_id)
             .order_by(RewardTier.min_amount.asc())
             .all())
    total = user_total_for_project(user_id, project_id)

    progress = []
    next_needed = None
    for t in tiers:
        achieved = total >= t.min_amount
        missing = max(0, t.min_amount - total)
        progress.append({
            "tier_id": t.id,
            "name": t.description,
            "min_amount": t.min_amount,
            "qty_remaining": t.qty_remaining,
            "achieved": achieved,
            "missing": missing
        })
        if not achieved and next_needed is None:
            next_needed = missing

    highest = None
    for row in reversed(progress):
        if row["achieved"]:
            highest = row
            break

    return {
        "total": total,
        "tiers": progress,
        "next_missing": next_needed,
        "highest": highest
    }

# ---------------- Routes ----------------
@app.route('/')
def project_list():
    q = request.args.get('q', '')
    category = request.args.get('category')
    sort = request.args.get('sort', 'newest')

    query = Project.query
    if q:
        query = query.filter(Project.title.ilike(f"%{q}%"))
    if category:
        query = query.join(Category).filter(Category.name == category)

    if sort == 'newest':
        query = query.order_by(Project.created_at.desc())
    elif sort == 'ending_soon':
        query = query.order_by(Project.deadline.asc())
    elif sort == 'most_funded':
        query = query.order_by(Project.current_amount.desc())

    projects = query.all()
    categories = Category.query.all()
    return render_template('project_list.html',
                           projects=projects,
                           categories=categories,
                           q=q, category=category,
                           sort=sort,
                           user=current_user())

@app.route('/project/<project_id>')
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    leaderboard = get_leaderboard(project_id)
    user = current_user()
    tier_status = reward_progress_for_user(project_id, user.id) if user else None
    return render_template('project_detail.html',
                           project=project,
                           user=user,
                           leaderboard=leaderboard,
                           tier_status=tier_status)

@app.route('/pledge', methods=['POST'])
def make_pledge():
    if not current_user():
        flash('ต้องเข้าสู่ระบบก่อนการสนับสนุน')
        return redirect(url_for('login'))

    user = current_user()
    project_id = request.form.get('project_id')
    reward_tier_id = request.form.get('reward_tier_id') or None
    amount = int(request.form.get('amount', '0'))

    project = Project.query.get(project_id)
    if not project:
        flash('โครงการไม่พบ')
        return redirect(url_for('project_list'))

    pledge = Pledge(user_id=user.id, project_id=project.id,
                    amount=amount, time=datetime.utcnow())

    # Business rules
    now = datetime.utcnow()
    if project.deadline <= now:
        pledge.accepted = False
        pledge.rejected_reason = 'deadline_passed'
    else:
        reward = None
        if reward_tier_id:
            reward = RewardTier.query.get(int(reward_tier_id))
            if not reward or reward.project_id != project.id:
                pledge.accepted = False
                pledge.rejected_reason = 'invalid_reward'

        if reward and amount < reward.min_amount:
            pledge.accepted = False
            pledge.rejected_reason = 'amount_less_than_reward_min'
        elif reward and reward.qty_remaining is not None and reward.qty_remaining <= 0:
            pledge.accepted = False
            pledge.rejected_reason = 'reward_sold_out'
        elif amount <= 0:
            pledge.accepted = False
            pledge.rejected_reason = 'invalid_amount'
        else:
            pledge.accepted = True
            pledge.reward_tier_id = reward.id if reward else None
            project.current_amount += amount
            if reward and reward.qty_remaining is not None:
                reward.qty_remaining -= 1
            db.session.add(project)
            if reward:
                db.session.add(reward)

    db.session.add(pledge)
    db.session.commit()

    if pledge.accepted:
        flash('สนับสนุนเรียบร้อย')
    else:
        flash('การสนับสนุนถูกปฏิเสธ: ' + (pledge.rejected_reason or 'unknown'))
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/stats')
def stats():
    accepted_count = Pledge.query.filter_by(accepted=True).count()
    rejected_count = Pledge.query.filter_by(accepted=False).count()
    return render_template('stats.html',
                           accepted=accepted_count,
                           rejected=rejected_count,
                           user=current_user())

# ---------------- Auth ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            flash('เข้าสู่ระบบสำเร็จ')
            return redirect(url_for('project_list'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('ออกจากระบบแล้ว')
    return redirect(url_for('project_list'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('มีผู้ใช้ชื่อนี้แล้ว')
            return redirect(url_for('register'))
        u = User(username=username, password=password)
        db.session.add(u)
        db.session.commit()
        flash('สมัครสมาชิกเรียบร้อย')
        return redirect(url_for('login'))
    return render_template('register.html')

# ---------------- Run ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
