import pandas as pd
from sklearn.model_selection import cross_val_score, GridSearchCV, validation_curve
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_predict
from matplotlib import pyplot as plt


class ProjectResults:
    def __init__(self, project_name, results, scores, scores_text, confusion_matrix, target_names):
        self.project_name = project_name
        self.results = results
        self.scores = scores
        self.scores_text = scores_text
        self.confusion_matrix = confusion_matrix
        self.target_names = target_names

    def get_scores_df(self):
        return pd.DataFrame(self.scores).transpose()

    def get_confusion_matrix_df(self):
        print('Columns = predicted label')
        print('Rows = true label')
        return pd.DataFrame(self.confusion_matrix, index=self.target_names, columns=self.target_names)

class ProjectsResults:
    def __init__(self, algorithm, projects, non_feature_columns, drop_na=True):
        self.results = {}
        self.algorithm = algorithm
        self.evaluate_projects(projects, non_feature_columns, algorithm, drop_na)
    
    def add_project_result(self, project_result):
        self.results[project_result.project_name] = project_result

    def get_report_df(self, include_overall=False, sort_by='improvement'):
        results_df = []
        for project_name, project_results in self.results.items():
            results_df.append(project_results.results)
        df = pd.concat(results_df, ignore_index=True)
        df = df.sort_values(sort_by, ascending=False)
        if include_overall:
            df = pd.concat([df, get_overall_accuracy(df)], ignore_index=True)
        return df

    def evaluate_projects(self, projects, non_features_columns, algorithm, drop_na):
        for project in projects:
            project_results = evaluate_project(project, non_features_columns, algorithm, drop_na)
            self.add_project_result(project_results)
    
    def get_project(self, project_name):
        return self.results[project_name]



def get_majority_class_percentage(dataset, class_name):
    count = dataset[class_name].value_counts(normalize=True)
    if len(count>0):
        return count.iloc[0]
    else:
        return float('nan')
    
def get_normalized_improvement(accuracy, baseline_accuracy):
    if accuracy > baseline_accuracy:
        return (accuracy - baseline_accuracy) / (1 - baseline_accuracy)
    return (accuracy - baseline_accuracy) / baseline_accuracy

def get_project_class_distribution(project, normalized=True, drop_na=True):
    developer_decisions = ['Version 1', 'Version 2', 'Combination', 'ConcatenationV1V2', 
    'ConcatenationV2V1', 'Manual', 'None']
    
    row = [project]
    project = project.replace("/", "__")
    project_dataset = f"../../data/projects/{project}-training.csv"
    df = pd.read_csv(project_dataset)
    if drop_na:
        df_clean = df.dropna()
    else:
        df_clean = df
    count = df_clean['developerdecision'].value_counts(normalize=normalized)
    for decision in developer_decisions:
        value = 0
        try:
            if normalized:
                value = round(count[decision]*100,2)
            else:
                value = int(count[decision])
        except KeyError:
            pass
        row.append(value)
    df_columns = ['Project']
    df_columns.extend(developer_decisions)
    return pd.DataFrame([row], columns=df_columns)

def get_projects_class_distribution(projects, normalized=True, drop_na=True):
    results = []
    developer_decisions = ['Version 1', 'Version 2', 'Combination', 'ConcatenationV1V2', 
    'ConcatenationV2V1', 'Manual', 'None']
    for project in projects:
        results.append(get_project_class_distribution(project, normalized, drop_na))
    return pd.concat(results, ignore_index=True)
    # return pd.DataFrame(results, columns=df_columns)

# ignores projects that were not evaluated (accuracy = np.NaN)
def get_overall_accuracy(results):
    sum_observations = results['observations'].sum()
    sum_observations_wt_nan = results['observations (wt NaN)'].sum()
    mean_precision = results['precision'].mean()
    mean_recall = results['recall'].mean()
    mean_f1_score = results['f1-score'].mean()
    mean_accuracy = results['accuracy'].mean()
    mean_baseline = results['baseline (majority)'].mean()
    mean_improvement = results['improvement'].mean()
    rows = [['Overall', sum_observations, sum_observations_wt_nan, mean_precision,
    mean_recall, mean_f1_score, mean_accuracy, mean_baseline, mean_improvement]]
    result = pd.DataFrame(rows, columns=results.columns)
    return result

def predict(algorithm, X, y):
    y_pred = cross_val_predict(algorithm, X, y, cv=10)
    return y_pred

def get_prediction_scores(y, y_pred, target_names, output_dict=True):
    scores = classification_report(y, y_pred, target_names=target_names, digits=3, output_dict=output_dict)
    return scores

def compare_models(models, models_names, projects, non_features_columns):
    models_results = []
    for model in models:
        models_results.append(ProjectsResults(model, projects, non_features_columns))
    reports = []
    for model_results in models_results:
        reports.append(model_results.get_report_df(include_overall=True))
    if len(reports) > 0:
        df_result = reports[0].loc[(reports[0]['project']=='Overall')]
        df_result['model'] = None
        for i in range(1, len(reports)):
            df_model_overall_report = reports[i].loc[(reports[i]['project']=='Overall')]
            df_result = pd.concat([df_result, df_model_overall_report], ignore_index=True)
        
        model_index = 0
        for index, row in df_result.iterrows():
            df_result.at[index, 'model'] = models_names[model_index]
            model_index+=1
        
        return df_result
    
# obs about metrics used:
# weighted metrics: precision, recall, and f1-score
# Calculate metrics for each label (class), and find their average weighted by support (the number of true instances for each label).
# https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_fscore_support.html#sklearn.metrics.precision_recall_fscore_support
# macro metrics: Calculate metrics for each label, and find their unweighted mean. This does not take label imbalance into account.
def evaluate_project(project, non_features_columns, algorithm, drop_na=True):
    results = []
    project = project.replace("/", "__")
    project_dataset = f"../../data/projects/{project}-training.csv"
    df = pd.read_csv(project_dataset)
    if drop_na:
        df_clean = df.dropna()
    else:
        df_clean = df
    majority_class = get_majority_class_percentage(df_clean, 'developerdecision')
    scores = {}
    scores_text= ''
    conf_matrix = []
    target_names = sorted(df['developerdecision'].unique())
    if len(df_clean) >= 10:
        y = df_clean["developerdecision"].copy()
        df_clean = df_clean.drop(columns=['developerdecision'])
        df_clean = df_clean.drop(columns=non_features_columns)
        features = list(df_clean.columns)
        X = df_clean[features]
#         print(f"project: {project} \t len df: {len(df)} \t len df clean: {len(df_clean)} \t len x: {len(X)}  \t len y: {len(y)}")
        # scores = cross_val_score(model, X, y, cv=10)
        # accuracy = scores.mean()
        # std_dev = scores.std()
        y_pred = predict(algorithm, X, y)
        scores = get_prediction_scores(y, y_pred, target_names)
        scores_text = get_prediction_scores(y, y_pred, target_names, False)
        conf_matrix = confusion_matrix(y, y_pred, labels=target_names)
        
        accuracy = scores['accuracy']
        precision = scores['weighted avg']['precision']
        recall = scores['weighted avg']['recall']
        f1_score = scores['weighted avg']['f1-score']
        normalized_improvement = get_normalized_improvement(accuracy, majority_class)
        
        results.append([project, len(df), len(df_clean), precision, recall, f1_score, accuracy, majority_class, normalized_improvement])
    else:
        results.append([project, len(df), len(df_clean), np.NaN, np.NaN, np.NaN, np.NaN, np.NaN, np.NaN])
    results = pd.DataFrame(results, columns=['project', 'observations', 'observations (wt NaN)', 'precision', 'recall', 'f1-score', 'accuracy', 'baseline (majority)', 'improvement'])
    
    results = results.round(3)
    return ProjectResults(project, results, scores, scores_text, conf_matrix, target_names)

# adapted from https://stackoverflow.com/questions/28200786/how-to-plot-scikit-learn-classification-report
def show_values(pc, fmt="%.2f", **kw):
    '''
    Heatmap with text in each cell with matplotlib's pyplot
    Source: https://stackoverflow.com/a/25074150/395857 
    By HYRY
    '''
    pc.update_scalarmappable()
    ax = pc.axes
    #ax = pc.axes# FOR LATEST MATPLOTLIB
    #Use zip BELOW IN PYTHON 3
    for p, color, value in zip(pc.get_paths(), pc.get_facecolors(), pc.get_array()):
        x, y = p.vertices[:-2, :].mean(0)
        if np.all(color[:3] > 0.5):
            color = (0.0, 0.0, 0.0)
        else:
            color = (1.0, 1.0, 1.0)
        ax.text(x, y, fmt % value, ha="center", va="center", color=color, **kw)

# adapted from https://stackoverflow.com/questions/28200786/how-to-plot-scikit-learn-classification-report
def cm2inch(*tupl):
    '''
    Specify figure size in centimeter in matplotlib
    Source: https://stackoverflow.com/a/22787457/395857
    By gns-ank
    '''
    inch = 2.54
    if type(tupl[0]) == tuple:
        return tuple(i/inch for i in tupl[0])
    else:
        return tuple(i/inch for i in tupl)

# adapted from https://stackoverflow.com/questions/28200786/how-to-plot-scikit-learn-classification-report
def heatmap(AUC, title, xlabel, ylabel, xticklabels, yticklabels, figure_width=40, figure_height=20, correct_orientation=False, cmap='RdBu'):
    '''
    Inspired by:
    - https://stackoverflow.com/a/16124677/395857 
    - https://stackoverflow.com/a/25074150/395857
    '''

    # Plot it out
    fig, ax = plt.subplots()    
    #c = ax.pcolor(AUC, edgecolors='k', linestyle= 'dashed', linewidths=0.2, cmap='RdBu', vmin=0.0, vmax=1.0)
    c = ax.pcolor(AUC, edgecolors='k', linestyle= 'dashed', linewidths=0.2, cmap=cmap)

    # put the major ticks at the middle of each cell
    ax.set_yticks(np.arange(AUC.shape[0]) + 0.5, minor=False)
    ax.set_xticks(np.arange(AUC.shape[1]) + 0.5, minor=False)

    # set tick labels
    #ax.set_xticklabels(np.arange(1,AUC.shape[1]+1), minor=False)
    ax.set_xticklabels(xticklabels, minor=False, color='black')
    ax.set_yticklabels(yticklabels, minor=False, color='black')

    fig.patch.set_facecolor('white')

    # set title and x/y labels
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)      

    # Remove last blank column
    plt.xlim( (0, AUC.shape[1]) )

    # Turn off all the ticks
    ax = plt.gca()    
    for t in ax.xaxis.get_major_ticks():
        t.tick1On = False
        t.tick2On = False
    for t in ax.yaxis.get_major_ticks():
        t.tick1On = False
        t.tick2On = False

    # Add color bar
    plt.colorbar(c)

    # Add text in each cell 
    show_values(c)

    # Proper orientation (origin at the top left instead of bottom left)
    if correct_orientation:
        ax.invert_yaxis()
        ax.xaxis.tick_top()       

    # resize 
    fig = plt.gcf()
    #fig.set_size_inches(cm2inch(40, 20))
    #fig.set_size_inches(cm2inch(40*4, 20*4))
    fig.set_size_inches(cm2inch(figure_width, figure_height))


# adapted from https://stackoverflow.com/questions/28200786/how-to-plot-scikit-learn-classification-report
def plot_classification_report(classification_report, title='Classification report ', cmap='RdBu'):
    '''
    Plot scikit-learn classification report.
    Extension based on https://stackoverflow.com/a/31689645/395857 
    '''

    plotMat = []
    support = []
    class_names = []

    not_classes = ['accuracy', 'macro avg', 'weighted avg']
    for class_name, metrics in classification_report.items():
            row_values = []
            if class_name not in not_classes:
                class_names.append(class_name)
                for metric, value in classification_report[class_name].items():
                    if metric != 'support':
                        row_values.append(float(value))
                    else:
                        support.append(value)
                plotMat.append(row_values)


    # print('plotMat: {0}'.format(plotMat))
    # print('support: {0}'.format(support))

    xlabel = 'Metrics'
    ylabel = 'Classes'
    xticklabels = ['Precision', 'Recall', 'F1-score']
    yticklabels = ['{0} ({1})'.format(class_names[idx], sup) for idx, sup  in enumerate(support)]
    figure_width = 25
    figure_height = len(class_names) + 7
    correct_orientation = False
    heatmap(np.array(plotMat), title, xlabel, ylabel, xticklabels, yticklabels, figure_width, figure_height, correct_orientation, cmap=cmap)

'''
    Assigns gold, silver, and bronze medals for the top-3 combination of parameters in each project.
'''
def grid_search_all(projects, estimator, parameters, non_features_columns):
    import itertools
    results = {}
    results_columns = list(parameters.keys())
    results_columns.extend(['mean_accuracy', 'sum_accuracy', 'total_medals', 'gold_medals', 'silver_medals', 'bronze_medals'])
    combinations = []

    for combination in itertools.product(*parameters.values()):
        row = []
        key=''
        for parameter_value in combination:
            row.append(parameter_value)
            key+=str(parameter_value)
        row.extend([0,0,0,0,0,0])
        combinations.append(row)
    results = pd.DataFrame(combinations, columns=results_columns)
        
    for project in projects:
        project_results = grid_search(project, estimator, parameters, non_features_columns)
        if project_results != None:
            df_gridsearch_dt = pd.DataFrame(project_results)\
                .filter(regex=("param_.*|mean_test_score|std_test_score|rank_test_score"))\
                .sort_values(by=['rank_test_score'])
            
            top_3 = df_gridsearch_dt[df_gridsearch_dt['rank_test_score']<=3]

            for index, combination in top_3.iterrows():
                filtered_rows = results
                for parameter in list(parameters.keys()):
                    parameter_key = f'param_{parameter}'
                    combination_value = combination[parameter_key]
                    if combination[parameter_key] == None:
                        filtered_rows = filtered_rows[filtered_rows[parameter].isnull()]
                    else:
                        filtered_rows = filtered_rows[filtered_rows[parameter]==combination_value]

                if len(filtered_rows) > 0:
                    row = results.loc[filtered_rows.index]
                    sum_accuracy = row['sum_accuracy']
                    gold_medals = row['gold_medals']
                    silver_medals = row['silver_medals']
                    bronze_medals = row['bronze_medals']
                    
                    
                    results.at[filtered_rows.index, 'sum_accuracy'] = sum_accuracy + combination['mean_test_score']
                    if combination['rank_test_score'] == 1:
                        results.at[filtered_rows.index, 'gold_medals'] = gold_medals + 1
                    elif combination['rank_test_score'] == 2:
                        results.at[filtered_rows.index, 'silver_medals'] = silver_medals + 1
                    else:
                        results.at[filtered_rows.index, 'bronze_medals'] = bronze_medals + 1
                    results.at[filtered_rows.index, 'total_medals'] = gold_medals + silver_medals + bronze_medals + 1
    
    results['mean_accuracy'] = results['sum_accuracy'] / results['total_medals']
    results = results.drop(['sum_accuracy'], axis=1)

    return results



def grid_search(project, estimator, parameters, non_features_columns):
    proj = project.replace("/", "__")
    proj_dataset = f"../../data/projects/{proj}-training.csv"
    df_proj = pd.read_csv(proj_dataset)
    df_clean = df_proj.dropna()
    # print(f"Length of df_clean: {len(df_clean)}")
    if len(df_clean) >= 10:
        # majority_class = get_majority_class_percentage(df_clean, 'developerdecision')
        y = df_clean["developerdecision"].copy()
        df_clean_features = df_clean.drop(columns=['developerdecision']) \
                                    .drop(columns=non_features_columns)
        features = list(df_clean_features.columns)
        X = df_clean_features[features]
        clf = GridSearchCV(estimator, parameters, verbose=0, cv=10)
        clf.fit(X, y)
        # print("Best params and score:", clf.best_params_, clf.best_score_, '\n',
              # clf.cv_results_,
            #   sep='\n')
        return clf.cv_results_
    else:
        return None

def get_validation_curve_all(projects, estimator, param_name, param_range, non_features_columns):
    train_scores_mean = []
    train_scores_std = []
    test_scores_mean = []
    test_scores_std = []
    number_projects = 0
    for project in projects:
        proj = project.replace("/", "__")
        proj_dataset = f"../../data/projects/{proj}-training.csv"
        df_proj = pd.read_csv(proj_dataset)
        df_clean = df_proj.dropna()
        # print(f"Length of df_clean: {len(df_clean)}\n")
        if len(df_clean) >= 10:
            y = df_clean["developerdecision"].copy()
            df_clean_features = df_clean.drop(columns=['developerdecision']) \
                                        .drop(columns=non_features_columns)
            features = list(df_clean_features.columns)
            X = df_clean_features[features]
            train_scores, test_scores = validation_curve(estimator, X, y, param_name=param_name, param_range=param_range, cv=10)

            train_scores_mean.append(np.mean(train_scores, axis=1).tolist())
            train_scores_std.append(np.std(train_scores, axis=1).tolist())
            test_scores_mean.append(np.mean(test_scores, axis=1).tolist())
            test_scores_std.append(np.std(test_scores, axis=1).tolist())
            number_projects+=1


    train_scores_mean= np.mean(train_scores_mean, axis=0)
    train_scores_std= np.mean(train_scores_std, axis=0)
    test_scores_mean= np.mean(test_scores_mean, axis=0)
    test_scores_std= np.mean(test_scores_std, axis=0)

    plt.title(f"Accumulated Validation Curve with {type(estimator).__name__}.\n Number of projects: {number_projects}")
    plt.xlabel(param_name)
    plt.ylabel("Score")
    plt.ylim(0.0, 1.1)
    lw = 2
    if None in param_range:
        param_range.remove(None)
        param_range.insert(0,-1)
    plt.plot(param_range, train_scores_mean, label="Training score",
                color="darkorange", lw=lw)
    plt.fill_between(param_range, train_scores_mean - train_scores_std,
                        train_scores_mean + train_scores_std, alpha=0.2,
                        color="darkorange", lw=lw)
    plt.plot(param_range, test_scores_mean, label="Cross-validation score",
                color="navy", lw=lw)
    plt.fill_between(param_range, test_scores_mean - test_scores_std,
                        test_scores_mean + test_scores_std, alpha=0.2,
                        color="navy", lw=lw)
    plt.legend(loc="best")
    plt.show()

def plot_validation_curve(project, estimator, param_name, param_range, non_features_columns, ax):
    proj = project.replace("/", "__")
    proj_dataset = f"../../data/projects/{proj}-training.csv"
    df_proj = pd.read_csv(proj_dataset)
    df_clean = df_proj.dropna()
    if len(df_clean) >= 10:
        # majority_class = get_majority_class_percentage(df_clean, 'developerdecision')
        y = df_clean["developerdecision"].copy()
        df_clean_features = df_clean.drop(columns=['developerdecision']) \
                                    .drop(columns=non_features_columns)
        features = list(df_clean_features.columns)
        X = df_clean_features[features]
        train_scores, test_scores = validation_curve(estimator, X, y, param_name=param_name, param_range=param_range, cv=10)

        train_scores_mean = np.mean(train_scores, axis=1)
        train_scores_std = np.std(train_scores, axis=1)
        test_scores_mean = np.mean(test_scores, axis=1)
        test_scores_std = np.std(test_scores, axis=1)

        ax.set_title(f"{project} \n n={len(df_clean)}", wrap=True)
        ax.set_xlabel(param_name)
        # plt.xticks(param_range)
        ax.set_ylabel("Score")
        ax.set_ylim(0.0, 1.1)
        lw = 2
        if None in param_range:
            param_range = param_range.copy()
            param_range.remove(None)
            param_range.insert(0,-1)
        ax.plot(param_range, train_scores_mean, label="Training score",
                 color="darkorange", lw=lw)
        ax.fill_between(param_range, train_scores_mean - train_scores_std,
                         train_scores_mean + train_scores_std, alpha=0.2,
                         color="darkorange", lw=lw)
        ax.plot(param_range, test_scores_mean, label="Cross-validation score",
                 color="navy", lw=lw)
        ax.fill_between(param_range, test_scores_mean - test_scores_std,
                         test_scores_mean + test_scores_std, alpha=0.2,
                         color="navy", lw=lw)
        ax.legend(loc="best")
        return True
    return False

def plot_validation_curves(projects, estimator, parameter, param_range, non_features_columns):
    import math
   
    N = len(projects)
    cols = 4
    rows = int(math.ceil(N / cols))
    plt.figure(figsize=(15,4*rows))
    
    plot_index = 1
    for n in range(N):
        ax = plt.subplot(rows,cols, plot_index)
        has_data = plot_validation_curve(projects[n], estimator, parameter,
                                                param_range,
                                                non_features_columns, ax)
        if not has_data:
            ax.remove()
        else:
            plot_index+=1
    plt.tight_layout()
    plt.savefig(f'validation_curves_{type(estimator).__name__}_{parameter}.png', bbox_inches='tight')