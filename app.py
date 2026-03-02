
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
from collections import defaultdict
import mysql.connector
import random
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key'
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="timetable_db"
)

# Route to edit a timetable for a class
@app.route('/edit_timetable/<path:class_name>', methods=['GET', 'POST'])
def edit_timetable(class_name):
    if 'user' not in session:
        return redirect('/login')
    cursor = db.cursor()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods = [1, 2, 3, 4, 5]

    # Get all subject-staff mappings for this class and user
    cursor.execute("""
        SELECT subject_name, staff_name FROM staff_subjects_classes
        WHERE class_name=%s AND user_id = (SELECT id FROM users WHERE username = %s)
    """, (class_name, session['user']))
    mappings = cursor.fetchall()
    # Build subject -> [staff] mapping
    subject_staff_map = {}
    for subject, staff in mappings:
        if subject not in subject_staff_map:
            subject_staff_map[subject] = []
        if staff not in subject_staff_map[subject]:
            subject_staff_map[subject].append(staff)
    subjects = list(subject_staff_map.keys())
    # Build a unique staff list for this class so edit dropdowns can show all staff for the class
    staff_set = set()
    for staff_list_vals in subject_staff_map.values():
        for st in staff_list_vals:
            staff_set.add(st)
    staff_list = sorted(staff_set)

    if request.method == 'POST':
        # Update timetable entries with staff clash prevention
        clash_errors = []
        for day in days:
            for per in periods:
                subject_field = f"subject_{day}_{per}"
                staff_field = f"staff_{day}_{per}"
                subject = request.form.get(subject_field, '').strip()
                staff = request.form.get(staff_field, '').strip()
                if subject and staff:
                    # Check for staff clash: is this staff already assigned to another class at this day/period?
                    clash_cursor = db.cursor()
                    try:
                        clash_cursor.execute(
                            """
                            SELECT class_name FROM timetable
                            WHERE staff_name = %s AND day = %s AND period = %s
                            AND class_name != %s AND user_id = (SELECT id FROM users WHERE username = %s)
                            """,
                            (staff, day, per, class_name, session['user'])
                        )
                        clash_result = clash_cursor.fetchone()
                        if clash_result:
                            clash_errors.append(f"Staff '{staff}' already assigned to class '{clash_result[0]}' on {day} period {per}.")
                            continue  # Skip update for this slot
                        # No clash, update as normal
                        cursor.execute(
                            """
                            UPDATE timetable SET subject_name=%s, staff_name=%s
                            WHERE class_name=%s AND day=%s AND period=%s AND user_id = (SELECT id FROM users WHERE username = %s)
                            """,
                            (subject, staff, class_name, day, per, session['user'])
                        )
                    finally:
                        clash_cursor.close()
        db.commit()
        cursor.close()
        if clash_errors:
            flash('Some changes were not saved due to staff clashes:\n' + '\n'.join(clash_errors), 'danger')
            return redirect(url_for('edit_timetable', class_name=class_name))
        return redirect('/view_timetable')

    # GET: Show current timetable
    cursor.execute("""
        SELECT day, period, subject_name, staff_name FROM timetable
        WHERE class_name=%s AND user_id = (SELECT id FROM users WHERE username = %s)
    """, (class_name, session['user']))
    rows = cursor.fetchall()
    timetable = {(row[0], row[1]): (row[2], row[3]) for row in rows}
    cursor.close()
    return render_template(
        'edit_timetable.html',
        class_name=class_name,
        days=days,
        periods=periods,
        timetable=timetable,
        subjects=subjects,
        subject_staff_map=subject_staff_map
        , staff_list=staff_list
    )


# Route to render delete_mapping.html (user sees only their mappings, admin sees all and can filter)
@app.route('/delete_mapping', methods=['GET', 'POST'])
def delete_mapping():
    if 'user' not in session:
        return redirect('/login')
    cursor2 = db.cursor()
    try:
        if session.get('role') == 'admin':
            filter_user = request.args.get('username')
            if filter_user:
                cursor2.execute("SELECT id, staff_name, subject_name, class_name FROM staff_subjects_classes s JOIN users u ON s.user_id = u.id WHERE u.username = %s", (filter_user,))
            else:
                cursor2.execute("SELECT s.id, s.staff_name, s.subject_name, s.class_name, u.username FROM staff_subjects_classes s JOIN users u ON s.user_id = u.id")
        else:
            cursor2.execute("SELECT id, staff_name, subject_name, class_name FROM staff_subjects_classes WHERE user_id = (SELECT id FROM users WHERE username = %s)", (session['user'],))
        mappings = cursor2.fetchall()
    finally:
        cursor2.close()
    return render_template('delete_mapping.html', mappings=mappings)

# ✅ Helper Function to Insert Timetable Entry (always use a local cursor)
def _ins(cls, day, per, sub, stf):
    cursor2 = db.cursor()
    try:
        cursor2.execute("""
            INSERT INTO timetable (user_id, class_name, day, period, subject_name, staff_name)
            VALUES ((SELECT id FROM users WHERE username = %s), %s, %s, %s, %s, %s)
        """, (session['user'], cls, day, per, sub, stf))
        db.commit()
    finally:
        cursor2.close()

@app.route('/delete_mapping/<int:mapping_id>', methods=['POST'])
def delete_mapping_by_id(mapping_id):
    if 'user' not in session:
        return redirect('/login')
    # Get mapping details before deleting
    cursor2 = db.cursor()
    try:
        # Only allow user to delete their own mapping unless admin
        if session.get('role') == 'admin':
            cursor2.execute("SELECT staff_name, subject_name, class_name FROM staff_subjects_classes WHERE id = %s", (mapping_id,))
        else:
            cursor2.execute("SELECT staff_name, subject_name, class_name FROM staff_subjects_classes WHERE id = %s AND user_id = (SELECT id FROM users WHERE username = %s)", (mapping_id, session['user']))
        mapping = cursor2.fetchone()
        if mapping:
            staff_name, subject_name, class_name = mapping
            # Delete the mapping
            cursor2.execute("DELETE FROM staff_subjects_classes WHERE id = %s", (mapping_id,))
            db.commit()
            # After deleting, check if any mappings remain for this subject/class for this user
            if session.get('role') == 'admin':
                cursor2.execute("SELECT COUNT(*) FROM staff_subjects_classes WHERE subject_name = %s AND class_name = %s", (subject_name, class_name))
            else:
                cursor2.execute("SELECT COUNT(*) FROM staff_subjects_classes WHERE subject_name = %s AND class_name = %s AND user_id = (SELECT id FROM users WHERE username = %s)", (subject_name, class_name, session['user']))
            count = cursor2.fetchone()[0]
            if count == 0:
                # No mappings remain, delete all timetable entries for this subject/class for this user
                if session.get('role') == 'admin':
                    cursor2.execute("DELETE FROM timetable WHERE subject_name = %s AND class_name = %s", (subject_name, class_name))
                else:
                    cursor2.execute("DELETE FROM timetable WHERE subject_name = %s AND class_name = %s AND user_id = (SELECT id FROM users WHERE username = %s)", (subject_name, class_name, session['user']))
                db.commit()
        else:
            # If mapping not found, just redirect
            return redirect('/delete_mapping')
    finally:
        cursor2.close()
    return redirect('/delete_mapping')

@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor2 = db.cursor()
        try:
            cursor2.execute("SELECT * FROM users WHERE username=%s", (username,))
            if cursor2.fetchone():
                return "Username already exists. Try another."
            cursor2.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'user')", (username, password))
            db.commit()
        finally:
            cursor2.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor2 = db.cursor()
        try:
            cursor2.execute("SELECT username, role FROM users WHERE username=%s AND password=%s", (username, password))
            user = cursor2.fetchone()
            if user:
                session['user'] = user[0]
                session['role'] = user[1]
                return redirect('/dashboard')
            return 'Invalid username or password'
        finally:
            cursor2.close()
        return render_template('login.html')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template('dashboard.html', user=session['user'])
    return redirect('/login')



@app.route('/college_panel', methods=['GET', 'POST'])
def college_panel():
    if 'user' not in session:
        return redirect('/login')
    return render_template('panel.html', user=session['user'], type="College")

@app.route('/generate_college_timetable', methods=['POST', 'GET'])
def generate_college_timetable():
    return run_timetabling(type="College", total_periods=5, skip_breaks=True, is_college=True)
def run_timetabling(type, total_periods, skip_breaks, is_college=False):
    # Strictly assign periods per week as per staff_subjects_classes, no over-assignment or auto-fill
    # Remove all previous timetable entries

    # Only delete this user's timetable (admin can delete all)
    cursor_del = db.cursor()
    try:
        if session.get('role') == 'admin':
            cursor_del.execute("DELETE FROM timetable")
        else:
            cursor_del.execute("DELETE FROM timetable WHERE user_id = (SELECT id FROM users WHERE username = %s)", (session['user'],))
        db.commit()
    finally:
        cursor_del.close()

    cursor_cls = db.cursor()
    try:
        if session.get('role') == 'admin':
            cursor_cls.execute("SELECT DISTINCT class_name FROM staff_subjects_classes")
        else:
            cursor_cls.execute("SELECT DISTINCT class_name FROM staff_subjects_classes WHERE user_id = (SELECT id FROM users WHERE username = %s)", (session['user'],))
        classes = [row[0] for row in cursor_cls.fetchall()]
    finally:
        cursor_cls.close()
    if not classes:
        return redirect('/assign_staff_subject')
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    total_periods_per_class = len(days) * total_periods

    # --- New logic: enforce lab blocks, periods_per_week, and staff clash prevention ---
    # Build a map of all staff assignments for clash checking
    staff_periods = defaultdict(lambda: defaultdict(lambda: defaultdict(str)))  # staff_periods[staff][day][period] = class
    diagnostic_msgs = []
    for cls in classes:
        cls_stripped = cls.strip()
        cursor2 = db.cursor()
        try:
            if session.get('role') == 'admin':
                cursor2.execute("SELECT staff_name, subject_name, periods_per_week FROM staff_subjects_classes WHERE class_name = %s", (cls_stripped,))
            else:
                cursor2.execute("SELECT staff_name, subject_name, periods_per_week FROM staff_subjects_classes WHERE class_name = %s AND user_id = (SELECT id FROM users WHERE username = %s)", (cls_stripped, session['user']))
            mappings = cursor2.fetchall()
        finally:
            cursor2.close()
        labs = []
        nonlabs = []
        for stf, sub, ppw in mappings:
            if 'lab' in sub.lower():
                labs.append((stf, sub, ppw))
            else:
                nonlabs.append((stf, sub, ppw))
        timetable_grid = {(day, per): None for day in days for per in range(1, total_periods+1)}
        if 'global_lab_blocks_used' not in locals():
            global_lab_blocks_used = {day: {'3': set(), '2': set()} for day in days}
        lab_days_used = set()
        unscheduled_lab_blocks = 0
        total_lab_blocks = 0
        unscheduled_lab_details = []
        for stf, sub, ppw in labs:
            blocks = []
            temp = ppw
            while temp > 0:
                if temp >= 3:
                    blocks.append(3)
                    temp -= 3
                elif temp == 2:
                    blocks.append(2)
                    temp -= 2
                else:
                    temp -= 1
            used_days_for_this_lab = set()
            for block_size in blocks:
                total_lab_blocks += 1
                assigned = False
                fail_reasons = []
                for day in days:
                    if day in lab_days_used or day in used_days_for_this_lab:
                        continue
                    if block_size == 3:
                        block_periods = [1,2,3]
                        block_key = '3'
                    elif block_size == 2:
                        block_periods = [4,5]
                        block_key = '2'
                    else:
                        continue
                    if cls_stripped in global_lab_blocks_used[day][block_key]:
                        continue
                    if len(global_lab_blocks_used[day][block_key]) > 0:
                        continue
                    staff_clash = False
                    for per in block_periods:
                        if staff_periods[stf][day][per] != '':
                            staff_clash = True
                    if staff_clash:
                        continue
                    if not all(timetable_grid[(day, per)] is None for per in block_periods):
                        continue
                    for per in block_periods:
                        timetable_grid[(day, per)] = (stf, sub)
                        staff_periods[stf][day][per] = cls_stripped
                    assigned = True
                    lab_days_used.add(day)
                    used_days_for_this_lab.add(day)
                    global_lab_blocks_used[day][block_key].add(cls_stripped)
                    break
                if not assigned:
                    unscheduled_lab_blocks += 1
                    unscheduled_lab_details.append(f"Lab block for {sub} ({stf}), size {block_size}:\n" + '\n'.join(fail_reasons))
        # Build a quota dict for (sub, stf): how many times it can appear (periods_per_week)
        nonlab_slots = []
        quota = {}
        language_slots = []
        language_quota = {}
        other_slots = []
        other_quota = {}
        for stf, sub, ppw in nonlabs:
            if sub.strip().lower() in ("tamil", "english"):
                language_slots.extend([(stf, sub)] * ppw)
                language_quota[(stf, sub)] = ppw
            else:
                other_slots.extend([(stf, sub)] * ppw)
                other_quota[(stf, sub)] = ppw
        # Shuffle subject order for randomness
        random.shuffle(language_slots)
        random.shuffle(other_slots)
        # Shuffle days for randomness in assignment
        days_shuffled = days.copy()
        random.shuffle(days_shuffled)
        slot_idx_lang = 0
        slot_idx_other = 0
        if len(language_slots) + len(other_slots) == 0:
            diagnostic_msgs.append(f"Class '{cls_stripped}': No non-lab subjects mapped. All non-lab periods will be 'Free'. Please add regular subjects for a complete timetable.")
        else:
            from collections import Counter
            assigned_overall_lang = Counter()
            assigned_overall_other = Counter()
            # 1. Distribute language subjects: at most one period per day per language subject, strictly by periods_per_week
            # For each language subject, assign exactly periods_per_week days, never more than one per day
            # Assign each language subject exactly periods_per_week times, never more than once per day
            lang_days = days.copy()
            for (stf, sub), quota_val in language_quota.items():
                assigned_days = set()
                attempts = 0
                while len(assigned_days) < quota_val and attempts < 100:
                    available_days = [d for d in lang_days if d not in assigned_days]
                    if not available_days:
                        break
                    day = random.choice(available_days)
                    # Only assign if this language subject is not already assigned for this day
                    if any(timetable_grid[(day, per)] is not None and timetable_grid[(day, per)][1].strip().lower() == sub.strip().lower() for per in range(1, total_periods+1)):
                        attempts += 1
                        continue
                    # Only assign if no other language subject is already assigned for this day
                    if any(timetable_grid[(day, per)] is not None and timetable_grid[(day, per)][1].strip().lower() in ("tamil", "english") for per in range(1, total_periods+1)):
                        attempts += 1
                        continue
                    free_periods = [per for per in range(1, total_periods+1)]
                    random.shuffle(free_periods)
                    free_periods = [per for per in free_periods if timetable_grid[(day, per)] is None and staff_periods[stf][day][per] == '']
                    if not free_periods:
                        attempts += 1
                        continue
                    per = free_periods[0]
                    timetable_grid[(day, per)] = (stf, sub)
                    staff_periods[stf][day][per] = cls_stripped
                    assigned_overall_lang[(stf, sub)] += 1
                    assigned_days.add(day)
                    attempts += 1
            # 2. Distribute other subjects: strictly at most one per day per subject
            for (stf, sub), quota_val in other_quota.items():
                used = 0
                days_for_subject = days.copy()
                random.shuffle(days_for_subject)
                for day in days_for_subject:
                    if used >= quota_val:
                        break
                    # Only one of this subject per day
                    if any(timetable_grid[(day, per)] is not None and timetable_grid[(day, per)][1] == sub for per in range(1, total_periods+1)):
                        continue
                    free_periods = [per for per in range(1, total_periods+1)]
                    random.shuffle(free_periods)
                    free_periods = [per for per in free_periods if timetable_grid[(day, per)] is None and staff_periods[stf][day][per] == '']
                    if not free_periods:
                        continue
                    per = free_periods[0]
                    timetable_grid[(day, per)] = (stf, sub)
                    staff_periods[stf][day][per] = cls_stripped
                    assigned_overall_other[(stf, sub)] += 1
                    used += 1
            # 3. If any slots remain, fill with any subject that still has quota left (should not happen if mapping is perfect)
            for day in days:
                for per in range(1, total_periods+1):
                    if timetable_grid[(day, per)] is None:
                        # Try language first
                        available_lang = [pair for pair in language_quota if assigned_overall_lang[pair] < language_quota[pair]]
                        if available_lang:
                            stf, sub = available_lang[0]
                            # ENFORCE: staff must not be assigned to any other class in this period
                            if staff_periods[stf][day][per] == '':
                                timetable_grid[(day, per)] = (stf, sub)
                                staff_periods[stf][day][per] = cls_stripped
                                assigned_overall_lang[(stf, sub)] += 1
                                continue
                        # Then try other subjects
                        available_other = [pair for pair in other_quota if assigned_overall_other[pair] < other_quota[pair]]
                        if available_other:
                            stf, sub = available_other[0]
                            if staff_periods[stf][day][per] == '':
                                timetable_grid[(day, per)] = (stf, sub)
                                staff_periods[stf][day][per] = cls_stripped
                                assigned_overall_other[(stf, sub)] += 1
        free_count = 0
        unscheduled_slots = []
        for day in days:
            for per in range(1, total_periods+1):
                if timetable_grid[(day, per)] is None:
                    unscheduled_slots.append((day, per))
        # If any unscheduled slots remain, try to fill them only from subjects that still have remaining quota
        if unscheduled_slots:
            # Build lists of subjects that still have quota left
            remaining_lang = [pair for pair in language_quota if assigned_overall_lang[pair] < language_quota[pair]]
            remaining_other = [pair for pair in other_quota if assigned_overall_other[pair] < other_quota[pair]]
            for (day, per) in unscheduled_slots:
                placed = False
                # Try to place a remaining language subject first
                for pair in remaining_lang:
                    stf, sub = pair
                    if staff_periods[stf][day][per] == '' and timetable_grid[(day, per)] is None:
                        timetable_grid[(day, per)] = (stf, sub)
                        staff_periods[stf][day][per] = cls_stripped
                        assigned_overall_lang[(stf, sub)] += 1
                        if assigned_overall_lang[(stf, sub)] >= language_quota[(stf, sub)]:
                            remaining_lang.remove(pair)
                        placed = True
                        break
                if placed:
                    continue
                # Then try other subjects with remaining quota
                for pair in remaining_other:
                    stf, sub = pair
                    if staff_periods[stf][day][per] == '' and timetable_grid[(day, per)] is None:
                        timetable_grid[(day, per)] = (stf, sub)
                        staff_periods[stf][day][per] = cls_stripped
                        assigned_overall_other[(stf, sub)] += 1
                        if assigned_overall_other[(stf, sub)] >= other_quota[(stf, sub)]:
                            remaining_other.remove(pair)
                        placed = True
                        break
                # If still not placed, mark as Free (do not over-assign)
                if not placed:
                    timetable_grid[(day, per)] = ('Free', '')
                    free_count += 1
        for (day, per), (stf, sub) in timetable_grid.items():
            _ins(cls_stripped, day, per, sub, stf)
        # Diagnostic summary for this class
        total_slots = len(days) * total_periods
        # Count assigned non-free periods from the timetable_grid (accurate per-class count)
        assigned_periods = sum(1 for (d, p), val in timetable_grid.items() if val is not None and val[0] != 'Free')
        if free_count > 0 or assigned_periods < total_slots:
            msg = f"Class '{cls_stripped}': {free_count} 'Free' periods. "
            if unscheduled_lab_blocks > 0:
                msg += f"{unscheduled_lab_blocks} lab block(s) could not be scheduled due to block constraints or staff/class clashes. "
            if assigned_periods < total_slots:
                msg += f"Only {assigned_periods} out of {total_slots} periods mapped. "
            # Extra diagnostics: show which slots are free
            msg += f" Free slots: {[f'{d} P{p}' for d,p in unscheduled_slots]}. "
            # List unscheduled lab details if any
            if unscheduled_lab_details:
                msg += "\nUnscheduled lab details:\n" + '\n'.join(unscheduled_lab_details)
            # Check if mapping covers all slots
            if assigned_periods < total_slots:
                msg += "\nPossible cause: The sum of periods_per_week in your mapping is less than the total required periods."
            elif unscheduled_lab_blocks > 0:
                msg += "\nPossible cause: Some labs could not be scheduled due to block constraints or staff/class clashes."
            else:
                msg += "\nPossible cause: Staff clash or no available slot for some subject."
            diagnostic_msgs.append(msg)
    # Show diagnostic summary as a flash message if any issues
    if diagnostic_msgs:
        flash('Timetable diagnostic summary:\n' + '\n'.join(diagnostic_msgs), 'warning')
    return redirect(f"/view_timetable?college={'1' if is_college else '0'}")

@app.route('/assign_staff_subject', methods=['GET', 'POST'])
def assign_staff_subject():
    if request.method == 'POST':
        staff = request.form['staff']
        subject = request.form['subject']
        class_name = request.form['class_name']
        periods_per_week = int(request.form['periods_per_week'])
        cursor_insert = db.cursor()
        try:
            cursor_insert.execute("""
                INSERT INTO staff_subjects_classes (user_id, staff_name, subject_name, class_name, periods_per_week)
                VALUES ((SELECT id FROM users WHERE username = %s), %s, %s, %s, %s)
            """, (session['user'], staff, subject, class_name, periods_per_week))
            db.commit()
        finally:
            cursor_insert.close()
        return """
        <div class='mapping-success-center'>
            <div class='mapping-success'><span class='checkmark'>&#x2705;</span> Data saved! <a class='add-more' href='/assign_staff_subject'>Add More</a></div>
        </div>
        <style>
            .mapping-success-center {
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 40vh;
            }
            .mapping-success {
                background: #e6ffe6;
                border: 1px solid #4CAF50;
                color: #222;
                padding: 10px 16px;
                margin: 16px 0;
                border-radius: 6px;
                font-size: 1.1em;
                display: inline-block;
                box-shadow: 0 2px 6px rgba(76,175,80,0.08);
            }
            .mapping-success .checkmark {
                color: #4CAF50;
                font-size: 1.2em;
                margin-right: 6px;
                vertical-align: middle;
            }
            .mapping-success .add-more {
                color: #1976d2;
                text-decoration: underline;
                margin-left: 8px;
                font-weight: 500;
                transition: color 0.2s;
            }
            .mapping-success .add-more:hover {
                color: #0d47a1;
            }
        </style>
        """
    # Always use a new cursor for SELECT in GET
    cursor_select = db.cursor()
    try:
        cursor_select.execute(
            "SELECT id, staff_name, subject_name, class_name, periods_per_week FROM staff_subjects_classes WHERE user_id = (SELECT id FROM users WHERE username = %s)",
            (session['user'],)
        )
        data = cursor_select.fetchall()
    finally:
        cursor_select.close()
    # Calculate total assigned periods for each class
    class_periods = defaultdict(int)
    diagnostics = {}
    required_periods = 6 * 5
    for row in data:
        class_periods[row[3]] += row[4]
    for cls, total in class_periods.items():
        if total < required_periods:
            diagnostics[cls] = f"❌ Only {total} periods mapped (need {required_periods}). Add more subjects or increase periods per week."
        elif total > required_periods:
            diagnostics[cls] = f"⚠️ {total} periods mapped (exceeds {required_periods}). Reduce periods per week."
        else:
            diagnostics[cls] = f"✅ Perfect mapping: {total} periods."
    return render_template('map_staff_subject_class.html', data=data, class_periods=class_periods, required_periods=required_periods, diagnostics=diagnostics)

@app.route('/view_timetable')
def view_timetable():
    if 'user' not in session:
        return redirect('/login')

    is_college = request.args.get('college') == '1'
    days_map = {
        'Monday': 'Day 1',
        'Tuesday': 'Day 2',
        'Wednesday': 'Day 3',
        'Thursday': 'Day 4',
        'Friday': 'Day 5',
        'Saturday': 'Day 6'
    }

    cursor2 = db.cursor()
    class_user_map = {}
    try:
        if session.get('role') == 'admin':
            filter_user = request.args.get('username')
            if filter_user:
                cursor2.execute("SELECT t.class_name, t.day, t.period, t.subject_name, t.staff_name, u.username FROM timetable t JOIN users u ON t.user_id = u.id WHERE u.username = %s", (filter_user,))
            else:
                cursor2.execute("SELECT t.class_name, t.day, t.period, t.subject_name, t.staff_name, u.username FROM timetable t JOIN users u ON t.user_id = u.id")
        else:
            cursor2.execute("SELECT class_name, day, period, subject_name, staff_name FROM timetable WHERE user_id = (SELECT id FROM users WHERE username = %s)", (session['user'],))
        records = cursor2.fetchall()
        timetable_dict = defaultdict(lambda: ['-' for _ in range(5)])
        class_max_period = defaultdict(int)
        if session.get('role') == 'admin':
            # Get all classes and their creators
            cursor2.execute("SELECT DISTINCT s.class_name, u.username FROM staff_subjects_classes s JOIN users u ON s.user_id = u.id")
            for row in cursor2.fetchall():
                class_user_map[row[0]] = row[1]
            all_classes = list(class_user_map.keys())
        else:
            cursor2.execute("SELECT DISTINCT class_name FROM staff_subjects_classes WHERE user_id = (SELECT id FROM users WHERE username = %s)", (session['user'],))
            all_classes = [row[0] for row in cursor2.fetchall()]
    finally:
        cursor2.close()

    # Build a map to collect all staff assigned to a class/day/period
    clash_map = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    if session.get('role') == 'admin':
        for cls, day, per, sub, stf, username in records:
            idx = per - 1
            clash_map[cls][day][idx].append((sub, stf))
            class_max_period[cls] = max(class_max_period[cls], per)
            # If not already in class_user_map, add it
            if cls not in class_user_map:
                class_user_map[cls] = username
    else:
        for cls, day, per, sub, stf in records:
            idx = per - 1
            clash_map[cls][day][idx].append((sub, stf))
            class_max_period[cls] = max(class_max_period[cls], per)

    free_periods_warning = {}
    no_timetable_classes = set()
    for cls in all_classes:
        # Check if this class has any timetable entries
        if session.get('role') == 'admin':
            has_entries = any((c == cls) for c, _, _, _, _, _ in records)
        else:
            has_entries = any((c == cls) for c, _, _, _, _ in records)
        if not has_entries:
            no_timetable_classes.add(cls)
            free_periods_warning[cls] = f"❌ No timetable created for class '{cls}'. Please generate or map subjects/staff."
            continue
        free_count = 0
        for day in days_map.keys():
            for idx in range(5):
                entries = clash_map[cls][day][idx]
                if not entries:
                    timetable_dict[(cls, day)][idx] = "-"
                    free_count += 1
                else:
                    formatted = '<br>'.join([f"{stf}<br>{sub}" for sub, stf in entries])
                    timetable_dict[(cls, day)][idx] = formatted
        if free_count == 6 * 5:
            free_periods_warning[cls] = f"❌ All periods are 'Free' for class '{cls}'. No subjects/staff mapped. Please add mappings."

    total_periods = 5
    all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    class_day_list = [(cls, day) for cls in all_classes for day in all_days]

    # Also fetch all subject-staff mappings for this user (for mapping check in template)
    cursor3 = db.cursor()
    try:
        if session.get('role') == 'admin':
            cursor3.execute("SELECT id, staff_name, subject_name, class_name, periods_per_week FROM staff_subjects_classes")
        else:
            cursor3.execute("SELECT id, staff_name, subject_name, class_name, periods_per_week FROM staff_subjects_classes WHERE user_id = (SELECT id FROM users WHERE username = %s)", (session['user'],))
        data = cursor3.fetchall()
    finally:
        cursor3.close()
    return render_template(
        'view_timetable.html',
        timetable=timetable_dict,
        class_day_list=class_day_list,
        total_periods=total_periods,
        is_college=is_college,
        days_map=days_map,
        free_periods_warning=free_periods_warning,
        no_timetable_classes=no_timetable_classes,
        data=data,
        class_user_map=class_user_map,
        is_admin=(session.get('role') == 'admin')
    )


@app.route('/delete_timetable', methods=['POST', 'GET'])
def delete_timetable():
    if 'user' not in session:
        return redirect('/login')
    cursor2 = db.cursor()
    try:
        cursor2.execute("DELETE FROM timetable")
        db.commit()
    finally:
        cursor2.close()
    return redirect('/dashboard')


@app.route('/delete_all_mappings', methods=['POST'])
def delete_all_mappings():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect('/login')
    cursor2 = db.cursor()
    try:
        cursor2.execute("DELETE FROM staff_subjects_classes")
        db.commit()
    finally:
        cursor2.close()
    return redirect('/assign_staff_subject')

    # ...existing code...

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# PDF download route for timetable
@app.route('/download_timetable_pdf', methods=['GET'])
def download_timetable_pdf():
    download_type = request.args.get('download_type', 'whole')
    filter_value = request.args.get('filter_value', '').strip()
    institution_name = request.args.get('institution_name', '').strip() or 'INSTITUTION NAME'
    buffer = io.BytesIO()
    from reportlab.lib.pagesizes import A4, landscape
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    from datetime import datetime
    # Improved professional margins and layout
    page_width, page_height = landscape(A4)
    margin_x = 100  # more left/right margin
    margin_y = page_height - 200  # increase top margin to move table further down
    cell_width = 100
    cell_height = 44
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    day_labels = ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6']
    periods = [1, 2, 3, 4, 5]

    def draw_table(pdf, title, table_data, subtitle=None, staff_name=None, institution_name='INSTITUTION NAME'):
        # Center table horizontally and vertically
        table_width = cell_width * (len(periods)+1)
        table_height = cell_height * (len(days)+1)
        table_x = (page_width - table_width) / 2
        table_y = margin_y
        # Institution name and headings
        y_cursor = page_height - 40  # Absolute top margin
        pdf.setFont("Helvetica-Bold", 26)
        pdf.drawCentredString(page_width/2, y_cursor, institution_name)
        y_cursor -= 25
        pdf.setFont("Helvetica", 15)
        pdf.drawCentredString(page_width/2, y_cursor, "Academic Year: 2025-2026")
        y_cursor -= 25
        # For staff timetable, show title and staff name on the same line
        if title == "Staff Timetable" and staff_name and staff_name.strip():
            pdf.setFont("Helvetica-Bold", 19)
            title_text = f"Staff Timetable - {staff_name}"
            pdf.drawCentredString(page_width/2, y_cursor, title_text)
            y_cursor -= 18
        else:
            pdf.setFont("Helvetica-Bold", 19)
            pdf.drawCentredString(page_width/2, y_cursor, title)
            y_cursor -= 18
        if subtitle:
            pdf.setFont("Helvetica", 12)
            pdf.drawCentredString(page_width/2, y_cursor, subtitle)
        # Table header
        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColorRGB(0.92, 0.92, 0.92)
        pdf.rect(table_x, table_y, cell_width, cell_height, fill=1, stroke=1)
        pdf.setFillColorRGB(0, 0, 0)
        pdf.drawCentredString(table_x + cell_width/2, table_y + cell_height/2, "Day Order")
        for i, per in enumerate(periods):
            pdf.setFillColorRGB(0.92, 0.92, 0.92)
            pdf.rect(table_x + cell_width * (i+1), table_y, cell_width, cell_height, fill=1, stroke=1)
            pdf.setFillColorRGB(0, 0, 0)
            pdf.drawCentredString(table_x + cell_width * (i+1) + cell_width/2, table_y + cell_height/2, f"Period {per}")
        # Table body: only draw rows for days with at least one non-empty period (for staff timetable)
        for row_idx, day in enumerate(days):
            # For staff timetable, skip row if all periods are empty
            if title.startswith("Staff Timetable"):
                if all(table_data.get((day, per), "-") == "-" for per in periods):
                    continue
            y_offset = cell_height * (row_idx+1)
            # Alternating row color
            if row_idx % 2 == 0:
                pdf.setFillColorRGB(0.98, 0.98, 1)
            else:
                pdf.setFillColorRGB(1, 1, 1)
            pdf.rect(table_x, table_y - y_offset, cell_width * (len(periods)+1), cell_height, fill=1, stroke=0)
            pdf.setFillColorRGB(0, 0, 0)
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawCentredString(table_x + cell_width/2, table_y - y_offset + cell_height/2, day_labels[row_idx])
            for col_idx, per in enumerate(periods):
                cell_x = table_x + cell_width * (col_idx+1)
                cell_y = table_y - y_offset
                val = table_data.get((day, per), "-")
                # Parse subject, staff, and class (for staff/class view, class is in staff; for class/whole, class is known)
                if '\n' in val:
                    subj, staff = val.split('\n', 1)
                else:
                    subj, staff = val, ''
                # For staff timetable, staff cell contains 'subject (class)'
                class_disp = ''
                if '(' in subj and subj.endswith(')'):
                    # e.g. "DBMS (3 bca A)"
                    try:
                        subj_main, class_disp = subj.rsplit('(', 1)
                        subj = subj_main.strip()
                        class_disp = class_disp.strip(') ')
                    except Exception:
                        class_disp = ''
                # Draw cell border (bold)
                pdf.setLineWidth(1.2)
                pdf.rect(cell_x, cell_y, cell_width, cell_height, fill=0, stroke=1)
                # Fit subject and class text inside cell
                max_text_width = cell_width - 8
                # Subject (bold, shrink if needed)
                pdf.setFont("Helvetica-Bold", 11)
                subj_disp = subj.strip()
                while pdf.stringWidth(subj_disp, "Helvetica-Bold", 11) > max_text_width and len(subj_disp) > 3:
                    subj_disp = subj_disp[:-1]
                if subj_disp != subj.strip():
                    subj_disp = subj_disp[:-3] + '...'
                pdf.drawCentredString(cell_x + cell_width/2, cell_y + cell_height/2 + 12, subj_disp)
                # Class name (below subject)
                if class_disp:
                    pdf.setFont("Helvetica", 9)
                    class_disp2 = class_disp
                    while pdf.stringWidth(class_disp2, "Helvetica", 9) > max_text_width and len(class_disp2) > 3:
                        class_disp2 = class_disp2[:-1]
                    if class_disp2 != class_disp:
                        class_disp2 = class_disp2[:-3] + '...'
                    pdf.drawCentredString(cell_x + cell_width/2, cell_y + cell_height/2 + 1, class_disp2)
                    staff_y = cell_y + cell_height/2 - 10
                else:
                    staff_y = cell_y + cell_height/2 + 1
                # Staff (smaller, shrink if needed)
                pdf.setFont("Helvetica", 9)
                staff_disp = staff.strip()
                while pdf.stringWidth(staff_disp, "Helvetica", 9) > max_text_width and len(staff_disp) > 3:
                    staff_disp = staff_disp[:-1]
                if staff_disp != staff.strip():
                    staff_disp = staff_disp[:-3] + '...'
                pdf.drawCentredString(cell_x + cell_width/2, staff_y, staff_disp)
        # Draw all grid lines (bold)
        pdf.setLineWidth(1.5)
        for i in range(len(periods)+2):
            x = table_x + cell_width * i
            pdf.line(x, table_y, x, table_y - cell_height * (len(days)+1))
        for j in range(len(days)+2):
            y = table_y - cell_height * j
            pdf.line(table_x, y, table_x + table_width, y)
        # Footer
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.setFillColorRGB(0.3, 0.3, 0.3)
        pdf.drawRightString(page_width - margin_x, table_y - cell_height * (len(days)+1) - 30,
            f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
        pdf.drawString(margin_x, table_y - cell_height * (len(days)+1) - 30, f"Page {pdf.getPageNumber()}")
        pdf.setFillColorRGB(0, 0, 0)

    cursor2 = db.cursor()
    try:
        if download_type == 'whole':
            cursor2.execute("SELECT DISTINCT class_name FROM timetable ORDER BY class_name")
            all_classes = [row[0] for row in cursor2.fetchall()]
            for cls in all_classes:
                cursor2.execute("SELECT day, period, subject_name, staff_name FROM timetable WHERE class_name=%s", (cls,))
                rows = cursor2.fetchall()
                table_data = {}
                for day, per, sub, stf in rows:
                    table_data[(day, per)] = f"{sub}\n{stf if stf else '-'}"
                draw_table(pdf, f"Class: {cls}", table_data, institution_name=institution_name)
                pdf.showPage()
        elif download_type == 'class' and filter_value:
            cursor2.execute("SELECT day, period, subject_name, staff_name FROM timetable WHERE class_name=%s", (filter_value,))
            rows = cursor2.fetchall()
            table_data = {}
            for day, per, sub, stf in rows:
                table_data[(day, per)] = f"{sub}\n{stf if stf else '-'}"
            draw_table(pdf, f"Class Timetable: {filter_value}", table_data, institution_name=institution_name)
            pdf.showPage()
        elif download_type == 'staff' and filter_value:
            staff_name = filter_value.strip()
            # Case-insensitive, space-insensitive match for staff name
            cursor2.execute("SELECT class_name, day, period, subject_name FROM timetable WHERE TRIM(LOWER(staff_name)) = %s", (staff_name.lower(),))
            rows = cursor2.fetchall()
            table_data = {}
            for cls, day, per, sub in rows:
                table_data[(day, per)] = f"{sub} ({cls})"
            # Show staff name only as header, not in table title
            draw_table(pdf, "Staff Timetable", table_data, staff_name=staff_name, institution_name=institution_name)
            pdf.showPage()
        else:
            pdf.drawString(margin_x, margin_y, "No data found or filter value missing.")
    finally:
        cursor2.close()
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="timetable.pdf", mimetype="application/pdf")

if __name__ == '__main__':

    print("✅ Flask server starting...")
    app.run(debug=True)
