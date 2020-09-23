from flask import render_template, url_for, send_from_directory, request, redirect, flash
from statstool_web.forms import SavegameSelectForm, OneSavegameSelectForm, MapSelectForm, TagSetupForm, NewNationForm, NationFormationForm
from statstool_web import app, db
from statstool_web.parserfunctions import edit_parse, parse
from statstool_web.models import *
from werkzeug.utils import secure_filename
import os
import secrets
from pathlib import Path
from sqlalchemy.orm import load_only
from sqlalchemy import asc, desc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sqlalchemy.exc import IntegrityError

@app.route("/", methods = ["GET", "POST"])
@app.route("/home", methods = ["GET", "POST"])
def home():
    institutions = ["basesave", "renaissance", "colonialism", "printing_press", "global_trade", "manufactories", "enlightenment", "industrialization", "endsave"]
    savegame_dict = {}
    for inst in institutions:
        savegame_dict[inst] = Savegame.query.filter_by(mp_id=1, institution=inst).first()
    return render_template("home.html", savegame_dict = savegame_dict)

@app.route("/mp_overview/<name>", methods = ["GET", "POST"])
def mp_overview(name):
    return render_template("mp_overview.html")

@app.route("/upload_savegames", methods = ["GET", "POST"])
def upload_savegames():
    form = SavegameSelectForm()
    if form.validate_on_submit():
        sg_ids = []
        Path(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])).mkdir(parents=True, exist_ok=True)
        for file, map_file in zip((request.files[form.savegame1.name],request.files[form.savegame2.name]),\
                            (request.files[form.savegame1_map.name],request.files[form.savegame2_map.name])):
            random = secrets.token_hex(8) + ".eu4"
            path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], random)
            file.save(path)

            if map_file:
                map_random = secrets.token_hex(8) + ".png"
                map_path = os.path.join(app.root_path, "static/maps", map_random)
                map_file.save(map_path)
            else:
                map_path = None
            try:
                playertags, tag_list = edit_parse(path)
                if map_path:
                    savegame = Savegame(file = random, map_file = map_random)
                else:
                    savegame = Savegame(file = random)
                for tag in tag_list:
                    if not Nation.query.get(tag):
                        if tag in app.config["LOCALISATION_DICT"].keys():
                            t = Nation(tag = tag, name = app.config["LOCALISATION_DICT"][tag])
                        else:
                            t = Nation(tag = tag, name = tag)
                        db.session.add(t)
                        db.session.commit()

                    savegame.nations.append(Nation.query.get(tag))
                    if tag in playertags:
                        savegame.player_nations.append(Nation.query.get(tag))

                db.session.add(savegame)
                db.session.commit()
                sg_ids.append(savegame.id)
            except AttributeError as e:
                print(e)
            except (IndexError, UnicodeDecodeError) as e:
                print(e)

        return redirect(url_for("setup", sg_id1 = sg_ids[0], sg_id2 = sg_ids[1]))
    return render_template("upload_savegames.html", form = form)

@app.route("/upload_one_savegame/<string:institution>", methods = ["GET", "POST"])
def upload_one_savegame(institution):
    form = OneSavegameSelectForm()
    if form.validate_on_submit():
        Path(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])).mkdir(parents=True, exist_ok=True)
        save_file = request.files[form.savegame.name]
        map_file = request.files[form.map.name]

        random = secrets.token_hex(8) + ".eu4"
        path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], random)
        save_file.save(path)

        if map_file:
            map_random = secrets.token_hex(8) + ".png"
            map_path = os.path.join(app.root_path, "static/maps", map_random)
            map_file.save(map_path)
        else:
            map_path = None
        try:
            playertags, tag_list = edit_parse(path)
            if map_path:
                savegame = Savegame(file = random, mp_id = 1, map_file = map_random, institution = institution)
            else:
                savegame = Savegame(file = random, mp_id = 1, institution = institution)
            for tag in tag_list:
                if not Nation.query.get(tag):
                    if tag in app.config["LOCALISATION_DICT"].keys():
                        t = Nation(tag = tag, name = app.config["LOCALISATION_DICT"][tag])
                    else:
                        t = Nation(tag = tag, name = tag)
                    db.session.add(t)
                    db.session.commit()

                savegame.nations.append(Nation.query.get(tag))
                if tag in playertags:
                    savegame.player_nations.append(Nation.query.get(tag))

            db.session.add(savegame)
            db.session.commit()
        except AttributeError as e:
            print(e)
        except (IndexError, UnicodeDecodeError) as e:
            print(e)
        return redirect(url_for("setup", sg_id1 = savegame.id))
    return render_template("upload_one_savegame.html", form = form)

@app.route("/upload_map/<int:sg_id>", methods = ["GET", "POST"])
def upload_map(sg_id):
    form = MapSelectForm()
    if form.validate_on_submit():
        Path(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])).mkdir(parents=True, exist_ok=True)
        map_file = request.files[form.map.name]
        map_random = secrets.token_hex(8) + ".png"
        map_path = os.path.join(app.root_path, "static/maps", map_random)
        map_file.save(map_path)
        savegame = Savegame.query.get(sg_id)
        savegame.map_file = map_random
        db.session.commit()
        return redirect(url_for("setup", sg_id1 = savegame.id))
    return render_template("upload_map.html", form = form)

@app.route("/setup/<int:sg_id1>", methods = ["GET", "POST"], defaults={'sg_id2': None})
@app.route("/setup/<int:sg_id1>/<int:sg_id2>", methods = ["GET", "POST"])
def setup(sg_id1,sg_id2 = None):
    form = TagSetupForm()
    old_savegame = Savegame.query.get(sg_id1)
    if sg_id2:
        new_savegame = Savegame.query.get(sg_id2)
        nations = set(old_savegame.player_nations + new_savegame.player_nations)
    else:
        nations = old_savegame.player_nations

    playertags =  sorted([(nation.tag,app.config["LOCALISATION_DICT"][nation.tag]) \
        if nation.tag in app.config["LOCALISATION_DICT"].keys() else (nation.tag,nation.tag) \
        for nation in nations], key = lambda x: x[1])
    if request.method == "GET":
        return render_template("setup.html", form = form, playertags = playertags,\
                sg_id1 = sg_id1, sg_id2 = sg_id2)
    if request.method == "POST":
        if sg_id2:
            old_tag_list = [nation.tag for nation in old_savegame.player_nations]
            new_tag_list = [nation.tag for nation in new_savegame.player_nations]
            for tag in new_tag_list:
                if tag in old_tag_list:
                    formation = NationFormation(old_savegame_id = sg_id1, new_savegame_id = sg_id2, old_nation_tag = tag, new_nation_tag = tag)
                    db.session.add(formation)
                elif tag in [nation.tag for nation in old_savegame.nations]:
                    old_savegame.player_nations.append(Nation.query.get(tag))
                    formation = NationFormation(old_savegame_id = sg_id1, new_savegame_id = sg_id2, old_nation_tag = tag, new_nation_tag = tag)
                    db.session.add(formation)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
            else:
                db.session.commit()
            return redirect(url_for("main", sg_id1 = sg_id1, sg_id2 = sg_id2))
        else:
            return redirect(url_for("home"))

@app.route("/setup/new_nation/<int:sg_id1>", methods = ["GET", "POST"], defaults={'sg_id2': None})
@app.route("/setup/new_nation/<int:sg_id1>/<int:sg_id2>", methods = ["GET", "POST"])
def new_nation(sg_id1,sg_id2 = None):
    form = NewNationForm()
    if sg_id2:
        playertags = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations]
        new_tag_list = [nation.tag for nation in Savegame.query.get(sg_id2).nations \
                if nation.tag not in playertags]
    else:
        playertags = [nation.tag for nation in Savegame.query.get(sg_id1).player_nations]
        new_tag_list = [nation.tag for nation in Savegame.query.get(sg_id1).nations \
                if nation.tag not in playertags]
    form.select.choices = \
        sorted([(tag,app.config["LOCALISATION_DICT"][tag]) \
        if tag in app.config["LOCALISATION_DICT"].keys() else (tag,tag) \
        for tag in new_tag_list], key = lambda x: x[1])
    if request.method == "POST":
        if sg_id2:
            sg = Savegame.query.get(sg_id2)
        else:
            sg = Savegame.query.get(sg_id1)
        if form.select.data not in sg.player_nations:
            sg.player_nations.append(Nation.query.get(form.select.data))
        db.session.commit()
        return redirect(url_for("setup", sg_id1 = sg_id1, sg_id2 = sg_id2))
    return render_template("new_nation.html", form = form)

@app.route("/setup/remove_nation/<int:sg_id1>/<string:tag>", methods = ["GET", "POST"], defaults={'sg_id2': None})
@app.route("/setup/remove_nation/<int:sg_id1>/<int:sg_id2>/<string:tag>", methods = ["GET", "POST"])
def remove_nation(sg_id1, tag, sg_id2 = None):
    if sg_id2:
        ids = [sg_id1,sg_id2]
    else:
        ids = [sg_id1]
    for id in ids:
        sg = Savegame.query.get(id)
        playertags = [nation.tag for nation in sg.player_nations]
        if tag in playertags:
            sg.player_nations.remove(Nation.query.get(tag))
            db.session.commit()
    return redirect(url_for("setup", sg_id1 = sg_id1, sg_id2 = sg_id2))

@app.route("/setup/remove_all/<int:sg_id1>", methods = ["GET", "POST"], defaults={'sg_id2': None})
@app.route("/setup/remove_all/<int:sg_id1>/<int:sg_id2>", methods = ["GET", "POST"])
def remove_all(sg_id1,sg_id2 = None):
    if sg_id2:
        ids = [sg_id1,sg_id2]
    else:
        ids = [sg_id1]
    for id in ids:
        sg = Savegame.query.get(id)
        sg.player_nations = []
        db.session.commit()
    return redirect(url_for("setup", sg_id1 = sg_id1, sg_id2 = sg_id2))

@app.route("/main/<int:sg_id1>/<int:sg_id2>", methods = ["GET", "POST"])
def main(sg_id1,sg_id2):
    for id in (sg_id1,sg_id2):
        savegame = Savegame.query.get(id)
        if not savegame.parse_flag:
            parse(savegame)
            os.remove(os.path.join(app.root_path, app.config["UPLOAD_FOLDER"], savegame.file))
    map = Savegame.query.get(sg_id2).map_file
    return render_template("main_layout.html", sg_id1 = sg_id1, sg_id2 = sg_id2, map = map)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/remove_nation_formation/<string:old>/<string:new>", methods = ["GET", "POST"])
def remove_nation_formation(sg_id1,sg_id2,old,new):
    formation = NationFormation.query.get((sg_id1,sg_id2,old,new))
    db.session.delete(formation)
    db.session.commit()
    return redirect(url_for("main", sg_id1 = sg_id1, sg_id2 = sg_id2))

@app.route("/main/<int:sg_id1>/<int:sg_id2>/configure", methods = ["GET", "POST"])
def configure(sg_id1,sg_id2):
    form = NationFormationForm()
    if request.method == "POST":
        formation = NationFormation(old_savegame_id = sg_id1, new_savegame_id = sg_id2, old_nation_tag = form.old_nation.data, new_nation_tag = form.new_nation.data)
        db.session.add(formation)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
        else:
            db.session.commit()

    old_savegame = Savegame.query.get(sg_id1)
    new_savegame = Savegame.query.get(sg_id2)
    old_tag_list = [nation.tag for nation in old_savegame.player_nations]
    new_tag_list = [nation.tag for nation in new_savegame.player_nations]
    for tag in new_tag_list:
        if tag in [nation.tag for nation in old_savegame.nations] and tag not in old_tag_list:
            old_savegame.player_nations.append(Nation.query.get(tag))

    old_matching_tags = [x.old_nation_tag for x in NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2).all()]
    new_matching_tags = [x.new_nation_tag for x in NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2).all()]
    old_tag_list = [nation.tag for nation in Savegame.query.get(sg_id1).player_nations if nation.tag not in old_matching_tags]
    new_tag_list = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations if nation.tag not in new_matching_tags]


    for field,tag_list in ((form.old_nation,old_tag_list), (form.new_nation,new_tag_list)):
        field.choices = \
            sorted([(tag,app.config["LOCALISATION_DICT"][tag]) \
            if tag in app.config["LOCALISATION_DICT"].keys() else (tag,tag) \
            for tag in tag_list], key = lambda x: x[1])

    nation_formations = []
    for x in NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2).all():
        if x.old_nation_tag in app.config["LOCALISATION_DICT"].keys():
            old_nation = app.config["LOCALISATION_DICT"][x.old_nation_tag]
        else:
            old_nation = x.old_nation_tag

        if x.new_nation_tag in app.config["LOCALISATION_DICT"].keys():
            new_nation = app.config["LOCALISATION_DICT"][x.new_nation_tag]
        else:
            new_nation = x.new_nation_tag
        nation_formations.append((old_nation, new_nation))
    map = Savegame.query.get(sg_id2).map_file
    return render_template("configure.html",sg_id1 = sg_id1, sg_id2 = sg_id2, form = form, nation_formations = nation_formations, map = map)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/overview_table", methods = ["GET", "POST"])
def overview_table(sg_id1,sg_id2):
    columns = ["great_power_score", "development", "effective_development", "navy_strength", "max_manpower", "income"]
    header_labels = ["Nation", "Great Power Score", "Development", "Effective Development", "Navy Strength", "Maximum Manpower", "Monthly Income"]
    nation_data = []
    nation_colors = []
    nation_tags = []
    for nation in Savegame.query.get(sg_id2).player_nations:
        data = NationSavegameData.query.filter_by(nation_tag = nation.tag, \
                savegame_id = sg_id2).with_entities(*columns).first()._asdict()
        nation_data.append(data)
        nation_colors.append( str(NationSavegameData.query.filter_by(nation_tag = nation.tag, \
                savegame_id = sg_id2).first().color))
        nation_tags.append(nation.tag)
    map = Savegame.query.get(sg_id2).map_file
    return render_template("table.html", sg_id1 = sg_id1, sg_id2 = sg_id2, \
        data = zip(nation_data,nation_tags,nation_colors), columns = columns, header_labels = header_labels, num_of_columns = 7, map = map)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/development", methods = ["GET", "POST"])
def development(sg_id1, sg_id2):
    old_year = Savegame.query.get(sg_id1).year
    new_year = Savegame.query.get(sg_id2).year
    tag_list = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations]
    image_files = []
    for category, column in zip(("development","effective_development"),(NationSavegameData.development,NationSavegameData.effective_development)):
        data_list = NationSavegameData.query.filter(NationSavegameData.nation_tag.in_(tag_list),\
                NationSavegameData.savegame_id == sg_id2).order_by(desc(column))
        category_plot(sg_id1, sg_id2, category, tag_list, data_list, NationSavegameData, "{0}: {1}-{2}".format(category.capitalize(),old_year, new_year))
        image_files.append(SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = category).first().filename)

    data, header_labels, columns = table_data("development", old_year, new_year, tag_list, sg_id1, sg_id2, int, NationSavegameData)
    map = Savegame.query.get(sg_id2).map_file
    return render_template("plot.html", sg_id1 = sg_id1, sg_id2 = sg_id2, image_files = image_files, data = data, header_labels = header_labels, columns = columns, map = map)

def category_plot(sg_id1, sg_id2, category, tag_list, data_list, model, title):
    plot = SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = category).first()
    if plot:
        return
    else:
        figure = plt.figure(title)
        figure.suptitle(title, fontsize = 20)

        plt.tick_params(axis='both', which='major', labelsize=8)
        plt.grid(True, axis="y")
        plt.minorticks_on()
        plt.gca().get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))

        delta_dev_list = []
        for data in data_list:
            data = data.__dict__
            if NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, new_nation_tag = data["nation_tag"]).first():
                plt.bar(data["nation_tag"], data[category], color = str(data["color"]), edgecolor = "grey", linewidth = 1)
                old_tag = NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, new_nation_tag = data["nation_tag"]).first().old_nation_tag
                delta_dev_list.append([data["nation_tag"],data[category] - model.query.filter_by(nation_tag = old_tag, savegame_id = sg_id1).first().__dict__[category]])

        delta_values = [x[1] for x in delta_dev_list]
        norm = plt.Normalize(min(delta_values), max(delta_values))
        color_list = plt.cm.RdYlGn(norm(delta_values))

        for i in range(len(delta_dev_list)):
            plt.bar(delta_dev_list[i][0], delta_dev_list[i][1], color = color_list[i], edgecolor = "grey", linewidth = 1)

        random = secrets.token_hex(8) + ".png"
        path = os.path.join(app.root_path, "static/plots", random)
        plt.savefig(path, dpi=200)
        filename = random
        plot = SavegamePlots(filename = filename, type = category, old_savegame_id = sg_id1, new_savegame_id = sg_id2)
        db.session.add(plot)
        db.session.commit()

def table_data(category, old_year, new_year, tag_list, sg_id1, sg_id2, data_type, model):
    header_labels = ["Nation",old_year,new_year,"Δ","%"]
    columns = [0,1,2,3]
    nation_data = []
    nation_tags = []
    nation_colors = []
    for new_tag in tag_list:
        data = []
        if NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, new_nation_tag = new_tag).first():
            old_tag = NationFormation.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, new_nation_tag = new_tag).first().old_nation_tag
            for id,tag in zip((sg_id1,sg_id2),(old_tag,new_tag)):
                value = model.query.filter_by(nation_tag = tag, savegame_id = id).first().__dict__[category]
                data.append(value)
            delta = data_type(round(data[1] - data[0],2))
            if data[0] != 0:
                percent = round((data[1]/data[0]-1)*100,2)
                if delta > 0:
                    delta = "+" + str(delta)
                if percent > 0:
                    percent = "+" + str(percent)
                percent = str(percent) + "%"
            else:
                percent = "---"
            data.append(delta)
            data.append(percent)
            nation_data.append(data)
            nation_colors.append(str(model.query.filter_by(nation_tag = new_tag, \
                    savegame_id = sg_id2).first().color))
            nation_tags.append(new_tag)
    return zip(nation_data,nation_tags,nation_colors), header_labels, columns

@app.route("/main/<int:sg_id1>/<int:sg_id2>/income", methods = ["GET", "POST"])
def income(sg_id1, sg_id2):
    old_year = Savegame.query.get(sg_id1).year
    new_year = Savegame.query.get(sg_id2).year
    tag_list = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations]
    income_list = NationSavegameData.query.filter(NationSavegameData.nation_tag.in_(tag_list),\
                NationSavegameData.savegame_id == sg_id2).order_by(desc(NationSavegameData.income))
    category_plot(sg_id1,sg_id2,"income", tag_list, income_list, NationSavegameData, "Income: {0}-{1}".format(old_year, new_year))
    image_file = SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = "income").first().filename

    data, header_labels, columns = table_data("income", old_year, new_year, tag_list, sg_id1, sg_id2, float, NationSavegameData)
    map = Savegame.query.get(sg_id2).map_file
    return render_template("plot.html", sg_id1 = sg_id1, sg_id2 = sg_id2, image_files = [image_file], data = data, header_labels = header_labels, columns = columns, map = map)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/max_manpower", methods = ["GET", "POST"])
def max_manpower(sg_id1, sg_id2):
    old_year = Savegame.query.get(sg_id1).year
    new_year = Savegame.query.get(sg_id2).year
    tag_list = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations]
    manpower_list = NationSavegameData.query.filter(NationSavegameData.nation_tag.in_(tag_list),\
                NationSavegameData.savegame_id == sg_id2).order_by(desc(NationSavegameData.max_manpower))
    category_plot(sg_id1,sg_id2,"max_manpower", tag_list, manpower_list, NationSavegameData, "Maximum Manpower: {0}-{1}".format(old_year, new_year))
    image_file = SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = "max_manpower").first().filename
    data, header_labels, columns = table_data("max_manpower", old_year, new_year, tag_list, sg_id1, sg_id2, int, NationSavegameData)
    map = Savegame.query.get(sg_id2).map_file
    return render_template("plot.html", sg_id1 = sg_id1, sg_id2 = sg_id2, image_files = [image_file], data = data, header_labels = header_labels, columns = columns, map = map)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/army_losses", methods = ["GET", "POST"])
def army_losses(sg_id1, sg_id2):
    old_year = Savegame.query.get(sg_id1).year
    new_year = Savegame.query.get(sg_id2).year
    tag_list = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations]
    image_files = []
    columns = ( NationSavegameArmyLosses.infantry,NationSavegameArmyLosses.cavalry,NationSavegameArmyLosses.artillery,\
                NationSavegameArmyLosses.combat,NationSavegameArmyLosses.attrition,NationSavegameArmyLosses.total)
    for category, column in zip(("Infantry", "Cavalry", "Artillery", "Combat", "Attrition", "Total"),columns):
        army_losses_list = NationSavegameArmyLosses.query.filter(NationSavegameArmyLosses.nation_tag.in_(tag_list),\
                    NationSavegameArmyLosses.savegame_id == sg_id2).order_by(desc(column))
        category_plot(sg_id1, sg_id2, category.lower(), tag_list, army_losses_list, NationSavegameArmyLosses, "Army Losses - {0}: {1}-{2}".format(category, old_year, new_year))
        image_files.append(SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = category.lower()).first().filename)
    data, header_labels, columns = table_data("total", old_year, new_year, tag_list, sg_id1, sg_id2, int, NationSavegameArmyLosses)
    map = Savegame.query.get(sg_id2).map_file
    return render_template("plot.html", sg_id1 = sg_id1, sg_id2 = sg_id2, image_files = image_files, data = data, header_labels = header_labels, columns = columns, map = map)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/income_over_time", methods = ["GET", "POST"])
def income_over_time(sg_id1, sg_id2):

    new_year = Savegame.query.get(sg_id2).year
    image_files = []
    for (old_year, category) in zip((1445,Savegame.query.get(sg_id1).year),("income_over_time_total","income_over_time_latest")):
        income_plot(category, old_year, new_year, sg_id1, sg_id2)
        image_files.append(SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = category).first().filename)
    map = Savegame.query.get(sg_id2).map_file
    return render_template("plot.html", sg_id1 = sg_id1, sg_id2 = sg_id2, image_files = image_files, map = map)

def income_plot(category, old_year, new_year, sg_id1, sg_id2):
    plot = SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2, type = category).first()
    if plot:
        return
    else:
        income_plot = plt.figure("Income-Plot:{0}-{1}".format(old_year,new_year))
        income_plot.suptitle("{0}-{1}".format(old_year,new_year), fontsize = 20)
        plt.grid(True, which="both")
        plt.minorticks_on()
        plt.xlabel("Year")
        plt.ylabel("Income Per Year")
        a = 0
        markers = ["o","v","^","<",">","s","p","*","+","x","d","D","h","H"]
        nation_tags = [nation.tag for nation in Savegame.query.get(sg_id2).player_nations]

        m = 0
        for tag in nation_tags:
            income_data = [(income.year,income.amount) for income in \
                    NationSavegameIncomePerYear.query.filter_by(nation_tag = tag, savegame_id = sg_id2).all() if income.year >= old_year]
            color = NationSavegameData.query.get((tag, sg_id2)).color
            marker = markers[a%len(markers)]
            plt.plot([x[0] for x in income_data], [x[1] for x in income_data], label=tag, color= str(color), linewidth=1.5, marker = marker, markersize = 3)
            if (n := max([y for (x,y) in income_data])) > m:
                m = n
            a += 1

        plt.axis([old_year, new_year, 0, m * 1.05])
        plt.legend(prop={'size': 8})

        random = secrets.token_hex(8) + ".png"
        path = os.path.join(app.root_path, "static/plots", random)
        plt.savefig(path, dpi=200)
        filename = random
        plot = SavegamePlots(filename = filename, type = category, old_savegame_id = sg_id1, new_savegame_id = sg_id2)
        db.session.add(plot)
        db.session.commit()

@app.route("/main/<int:sg_id1>/<int:sg_id2>/provinces", methods = ["GET", "POST"])
def provinces(sg_id1, sg_id2):
    columns = ["province_id", "base_tax", "base_production", "base_manpower", "development", "religion", "culture", "trade_power"]
    header_labels = ["Nation", "ID", "Name", "Steuer", "Produktion", "Mannstärke", "Entwicklung", "Religion", "Kultur", "Handelsmacht", "Handelsgut"]
    province_data = []
    nation_colors = []
    nation_tags = []
    for province in SavegameProvinces.query.filter_by(savegame_id = sg_id2).all():
        province = province.__dict__
        data = {x: province[x] for x in columns}
        owner = NationSavegameData.query.filter_by(nation_tag = province["nation_tag"], \
                savegame_id = sg_id2).first()
        if owner:
            nation_colors.append(str(owner.color))
        else:
            nation_colors.append("#ffffff")
        nation_tags.append(province["nation_tag"])
        trade_good_name = TradeGood.query.filter_by(id = province["trade_good_id"]).first().name
        data["trade_good_name"] = trade_good_name
        province = Province.query.filter_by(id = province["province_id"]).first()
        data["name"] = province.name
        province_data.append(data)

    columns.append("trade_good_name")
    columns.insert(1, "name")
    return render_template("province_table.html", sg_id1 = sg_id1, sg_id2 = sg_id2, \
        data = zip(province_data,nation_tags,nation_colors), columns = columns, header_labels = header_labels)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/army_battles", methods = ["GET", "POST"])
def army_battles(sg_id1, sg_id2):
    columns = ["date", "total_combatants", "total_losses", "attacker_country", "attacker_infantry", "attacker_cavalry", \
        "attacker_artillery", "attacker_total", "attacker_losses", "attacker_commander", \
        "defender_country", "defender_infantry", "defender_cavalry", \
        "defender_artillery", "defender_total", "defender_losses", "defender_commander"]
    header_labels = ["Datum", "Truppen", "Verluste", "Angreifer", "Inf", "Kav", "Art", "Gesamt", "Verluste", "General", \
        "Verteidiger", "Inf", "Kav", "Art", "Gesamt", "Verluste", "General"]
    battle_data = []
    nation_colors = []
    nation_tags = []
    for battle in ArmyBattle.query.filter_by(savegame_id = sg_id2).all():
        battle = battle.__dict__
        data = {x: [battle[x],"#ffffff"] for x in columns}
        for column in ("attacker_country","defender_country"):
            nation = NationSavegameData.query.filter_by(nation_tag = data[column][0], savegame_id = sg_id2).first()
            if nation:
                data[column][1] = str(nation.color)
        result = battle["result"]
        if result == "yes":
            data["attacker_commander"][1] = "00ff00"
            data["defender_commander"][1] = "ff0000"
        if result == "no":
            data["attacker_commander"][1] = "ff0000"
            data["defender_commander"][1] = "00ff00"
        battle_data.append(data)

    return render_template("army_battles_table.html", sg_id1 = sg_id1, sg_id2 = sg_id2, \
        data = battle_data, columns = columns, header_labels = header_labels)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/mana_spent", methods = ["GET", "POST"])
def mana_spent(sg_id1, sg_id2):
    columns = ["date", "total_combatants", "total_losses", "attacker_country", "attacker_infantry", "attacker_cavalry", \
        "attacker_artillery", "attacker_total", "attacker_losses", "attacker_commander", \
        "defender_country", "defender_infantry", "defender_cavalry", \
        "defender_artillery", "defender_total", "defender_losses", "defender_commander"]
    header_labels = ["Datum", "Truppen", "Verluste", "Angreifer", "Inf", "Kav", "Art", "Gesamt", "Verluste", "General", \
        "Verteidiger", "Inf", "Kav", "Art", "Gesamt", "Verluste", "General"]
    battle_data = []
    nation_colors = []
    nation_tags = []
    for battle in ArmyBattle.query.filter_by(savegame_id = sg_id2).all():
        battle = battle.__dict__
        data = {x: [battle[x],"#ffffff"] for x in columns}
        for column in ("attacker_country","defender_country"):
            nation = NationSavegameData.query.filter_by(nation_tag = data[column][0], savegame_id = sg_id2).first()
            if nation:
                data[column][1] = str(nation.color)
        result = battle["result"]
        if result == "yes":
            data["attacker_commander"][1] = "00ff00"
            data["defender_commander"][1] = "ff0000"
        if result == "no":
            data["attacker_commander"][1] = "ff0000"
            data["defender_commander"][1] = "00ff00"
        battle_data.append(data)

    return render_template("army_battles_table.html", sg_id1 = sg_id1, sg_id2 = sg_id2, \
        data = battle_data, columns = columns, header_labels = header_labels)

@app.route("/main/<int:sg_id1>/<int:sg_id2>/<list:image_files>/reload_plot", methods = ["GET", "POST"])
def reload_plot(sg_id1, sg_id2, image_files):
    for file in image_files:
        plot = SavegamePlots.query.get(file)
        db.session.delete(plot)
        try:
            os.remove(os.path.join(app.root_path, "static/plots", file))
        except FileNotFoundError:
            pass
    db.session.commit()
    return redirect(url_for("main", sg_id1 = sg_id1, sg_id2 = sg_id2))

@app.route("/main/<int:sg_id1>/<int:sg_id2>/reload_all_plotsplot", methods = ["GET", "POST"])
def reload_all_plots(sg_id1, sg_id2):
    plots = SavegamePlots.query.filter_by(old_savegame_id = sg_id1, new_savegame_id = sg_id2)
    for plot in plots:
        filename = plot.filename
        db.session.delete(plot)
        try:
            os.remove(os.path.join(app.root_path, "static/plots", filename))
        except FileNotFoundError:
            pass
    db.session.commit()
    return redirect(url_for("configure", sg_id1 = sg_id1, sg_id2 = sg_id2))

@app.route("/main/<int:sg_id1>/<int:sg_id2>/victory_points", methods = ["GET", "POST"])
def victory_points(sg_id1, sg_id2):
    columns = ["num_of_colonies", "standing_army", "navy_cannons"]
    header_labels = ["Nation", "Kolonialismus: meiste Kolonien", "Stehendes Heer", "Flotte: Gesamtanzahl Kanonen", "Armeeverluste im Kampf", "höchstentwickelte Provinz", "Siegpunkte"]
    nation_data = []
    nation_colors = []
    nation_tags = []
    for nation in Savegame.query.get(sg_id2).player_nations:
        data = NationSavegameData.query.filter_by(nation_tag = nation.tag, \
                savegame_id = sg_id2).with_entities(*columns).first()._asdict()
        nation_colors.append( str(NationSavegameData.query.filter_by(nation_tag = nation.tag, \
                savegame_id = sg_id2).first().color))
        nation_tags.append(nation.tag)

        losses = NationSavegameArmyLosses.query.filter_by(nation_tag = nation.tag, savegame_id = sg_id2).first().combat
        data["losses"] = losses

        highest_dev = SavegameProvinces.query.filter_by(\
            nation_tag = nation.tag, savegame_id = sg_id2).order_by(SavegameProvinces.development.desc()).first().development
        data["highest_dev"] = highest_dev
        data["victory_points"] = 0
        nation_data.append(data)

    columns += ["losses", "highest_dev", "victory_points"]
    nation_tags.append("Minimalwert")
    nation_colors.append("ffffff")
    nation_data.append({"num_of_colonies": 5, "standing_army": 100000, "navy_cannons": 2000, "losses": 500000, "highest_dev": 50})


    for category in ("standing_army", "navy_cannons", "losses", "highest_dev"):
        max_category = max([x[category] for x in nation_data])
        for data in nation_data[:-1]:
            if data[category] == max_category:
                if category == "highest_ae":
                    data["victory_points"] += 2
                else:
                    data["victory_points"] += 1


    return render_template("table.html", sg_id1 = sg_id1, sg_id2 = sg_id2, \
        data = zip(nation_data,nation_tags,nation_colors), columns = columns, header_labels = header_labels, num_of_columns = 7)

@app.route("/main/victory_points/<int:mp_id>", methods = ["GET", "POST"])
def total_victory_points(mp_id):
    savegame = Savegame.query.filter_by(mp_id = mp_id).order_by(desc(Savegame.year)).first()

    if savegame:
        header_labels = ["Nation", "Basis", "Kriege", "Renaissance", "Kolonialismus", "Druckerpresse", "Globaler Handel", "Manufakturen", "Aufklärung", "Industrialiserung", "Gesamt"]
        nation_tags = [x.tag for x in savegame.player_nations]
        nation_colors = [str(NationSavegameData.query.filter_by(nation_tag = tag, \
                savegame_id = savegame.id).first().color) for tag in nation_tags]
        data = {tag:[2,0,0,0,0,0,0,0,0] for tag in nation_tags}

        data["TUR"][0] = 1
        data["TUR"][2] = 2
        data["TUR"][3] = 1

        data["MOS"][0] = 1
        data["MOS"][1] = 3

        data["SWE"][1] = -2

        data["POL"][1] = -1

        for tag in data.keys():
            data[tag].append(sum(data[tag]))

        return render_template("victory_points.html", header_labels = header_labels, nation_info = zip(nation_tags,nation_colors), data = data)

    else:
        flash(f'Noch keine Siegpunkte vergeben.', 'danger')
        return redirect(url_for("home"))

@app.route("/main/latest_stats/<int:mp_id>", methods = ["GET", "POST"])
def latest_stats(mp_id):
    savegames = Savegame.query.filter_by(mp_id = mp_id).order_by(desc(Savegame.year)).all()
    if len(savegames) > 1:
        sg_id1 = savegames[1].id
        sg_id2 = savegames[0].id
        return redirect(url_for("main", sg_id1 = sg_id1, sg_id2 = sg_id2))
    else:
        flash(f'Noch keine Statistik verfügbar.', 'danger')
        return redirect(url_for("home"))


@app.route('/colorize.js')
def colorize():
    return render_template('jquery-colorize.js')
