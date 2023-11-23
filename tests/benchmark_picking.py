# %%
from typing import Any, Callable
import numpy as np
import pandas as pd
from scoary.picking import pick, pick_nonrecursive, pick_single
from scoary.permutations import create_permuted_df, permute_picking
from scoary.scoary_1_picking import convert_upgma_to_phylotree

import random
from timeit import default_timer as timer

# %%

boolify = lambda t1, t2: f"{'A' if t1 else 'a'}{'B' if t2 else 'b'}"


def time_fn(fn: Callable, args=None, kwargs=None, n_times: int = 1) -> (float, Any):
    if kwargs is None:
        kwargs = {}
    if args is None:
        args = []

    diffs = []
    for i in range(n_times):
        start = timer()
        res = fn(*args, **kwargs)
        end = timer()
        diffs.append(end - start)  # Time in seconds, e.g. 5.38091952400282
    return np.mean(diffs), res


def scoary_1_pick(tree: [], label_to_trait_a: {str: bool}, trait_b_df: pd.DataFrame):
    labels = set(trait_b_df.columns)

    max_contrasting = np.empty(shape=len(trait_b_df), dtype='int')
    max_supporting = np.empty(shape=len(trait_b_df), dtype='int')
    max_opposing = np.empty(shape=len(trait_b_df), dtype='int')

    for i, (_, label_to_trait) in enumerate(trait_b_df.iterrows()):
        gtc = {l: boolify(label_to_trait_a[l], label_to_trait[l]) for l in labels}
        phylo_tree, result_dict = convert_upgma_to_phylotree(tree, gtc)

        max_contrasting[i] = result_dict['Total']
        max_supporting[i] = result_dict['Pro']
        max_opposing[i] = result_dict['Anti']

    return max_contrasting, max_supporting, max_opposing


def generate_random_tree(labels: [str]):
    labels = labels.copy()
    random.shuffle(labels)
    size = len(labels)
    assert size > 0, 'Trees must have at least one node. {size=}'

    def _generate_random_tree(size: int):
        if size == 0:
            return labels.pop()

        # Choose random sizes for left and right subtrees
        left_size = random.randint(0, size - 1)
        right_size = size - 1 - left_size

        # Generate left and right subtrees recursively
        return [_generate_random_tree(left_size), _generate_random_tree(right_size)]

    return _generate_random_tree(size - 1)


def generate_random_traits(isolates: [str], properties: [str]):
    # Specify the shape of the 2D array (e.g., 10 rows and 10 columns)
    shape = (len(properties), len(isolates))

    # Generate a 2D array of random proportions for each row
    # e.g. [[0.2018124501276919], [0.3881403490748617], [0.06143480247664834], ...]
    row_proportions = np.random.random(shape[0])[:, np.newaxis]

    # Generate a random array of the same shape as 'shape'
    random_values = np.random.random(shape)

    # Return a boolean array where values are compared to row-specific proportions
    return pd.DataFrame(random_values < row_proportions, columns=isolates, index=properties)


def generate_dataset(n_isolates: int, n_genes: int, proportion: float = 0.5):
    # generate dummy data
    isolates = [f'i{i}' for i in range(1, n_isolates + 1)]

    tree = generate_random_tree(isolates)

    genes_df = generate_random_traits(isolates, [f'g{i}' for i in range(1, n_genes + 1)])

    # trait_df = generate_random_traits(isolates, [f't{i}' for i in range(1, n_traits + 1)])
    trait = {f'i{i}': bool(t) for i, t in enumerate(np.random.binomial(1, proportion, size=n_isolates), start=1)}

    return tree, trait, genes_df


def benchmark(n_isolates: [int], n_genes: [int], n_times: int = 3, df: pd.DataFrame = None):
    if df is None:
        df = pd.DataFrame(columns=['n_isolates', 'n_genes', 'scoary', 'scoary2'])

    for n_i in n_isolates:
        for n_g in n_genes:
            if ((df['n_isolates'] == n_i) & (df['n_genes'] == n_g)).any():
                continue

            tree, trait, genes_df = generate_dataset(n_isolates=n_i, n_genes=n_g)

            time_1, res = time_fn(
                scoary_1_pick,
                kwargs=dict(tree=tree, label_to_trait_a=trait, trait_b_df=genes_df),
                n_times=n_times
            )
            mc_1, ms_1, mo_1 = res

            time_2, res = time_fn(
                pick,
                kwargs=dict(tree=tree, label_to_trait_a=trait, trait_b_df=genes_df, calc_pvals=False),
                n_times=n_times
            )
            mc_2, ms_2, mo_2 = res

            df.loc[len(df)] = dict(n_isolates=n_i, n_genes=n_g, scoary=time_1, scoary2=time_2)

            print(f'{n_i}ix{n_g}g | S1:{time_1}sec | S2:{time_2} | {time_1 / time_2}x improvement')

            assert all(np.equal(mc_1, mc_2)), 'contrasting'
            assert all(np.equal(ms_1, ms_2)), 'supporting'
            assert all(np.equal(mo_1, mo_2)), 'opposing'

    return df


# %%

# jit compile
pick(*generate_dataset(n_isolates=5, n_genes=5), calc_pvals=False)

# df = benchmark(n_isolates=[5, 10, 20, 30, 40], n_genes=[10, 50, 100, 200, 400], n_times=1)
# df = benchmark(n_isolates=[5, 10, 20, 50, 100, 200, 1_000, 5_000, 10_000], n_genes=[10, 100, 1000, 5_000, 10_000], n_times=1)
df = benchmark(n_isolates=range(5, 101, 5), n_genes=range(5, 101, 5), n_times=5)

print(df)

df.to_csv('TMP/benchmark2.tsv', sep='\t')

# %%
df = pd.read_csv('TMP/benchmark2.tsv', sep='\t', index_col=0)

import matplotlib as mpl

# use default mpl backend
mpl.use('module://backend_interagg')

from matplotlib import pyplot as plt
from matplotlib.ticker import FuncFormatter


# %%

def plot(
        df: pd.DataFrame,
        x: str, y: str,
        zs: [tuple],
        xlog: bool = False, ylog: bool = False, zlog: bool = False,
        azim: int = -98,
        figsize: tuple = (12, 12), dpi: int = 300,
        save_path: str = None
):
    plt.close()
    fig = plt.figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111, projection='3d')

    _x = df[x].values
    if xlog:
        _x = np.log10(_x)
    _y = df[y].values

    if ylog:
        _y = np.log10(_y)

    for z, color, cmap, alpha in zs:
        _z = df[z].values
        if zlog: _z = np.log10(_z)

        ax.plot_trisurf(_x, _y, _z, cmap=cmap, edgecolors='grey', alpha=alpha)
        ax.scatter(_x, _y, _z, cmap=cmap, label=z, c=color)

    ax.set_xlabel(x if not xlog else f'{x} (log)')
    ax.set_ylabel(y if not ylog else f'{y} (log)')
    ax.set_zlabel('time [s]' if not zlog else f'time [s] (log)')

    plt.legend()

    def log_formatter(x, pos):
        return f'$10^{{{x:.1g}}}$'

    if xlog:
        ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))

    if ylog:
        ax.yaxis.set_major_formatter(FuncFormatter(log_formatter))

    if zlog:
        ax.zaxis.set_major_formatter(FuncFormatter(log_formatter))

    ax.view_init(elev=6, azim=azim)

    if save_path:
        plt.savefig(save_path, dpi=300)
    else:
        plt.gcf().set_dpi(300)
        plt.tight_layout()
        plt.show()


# %%
plot(
    df,
    x='n_isolates',
    y='n_genes',
    zs=[
        ('scoary', 'darkred', plt.cm.Reds, 0.4),
        ('scoary2', 'darkblue', plt.cm.Blues, 0.4)
    ],
    azim=-80
)

# %%
for azim in range(0, 360, 1):
    plot(
        df,
        x='n_isolates',
        y='n_genes',
        zs=[
            ('scoary', 'darkred', plt.cm.Reds, 0.4),
            ('scoary2', 'darkblue', plt.cm.Blues, 0.4)
        ],
        azim=azim,
        save_path=f'TMP/benchmark2/{azim:03d}.png'
    )
# ffmpeg -i benchmark2/%03d.png -c:v libx264 -r 30 -pix_fmt yuv420p out.mp4

# %%
for experiment in ['scoary', 'scoary2']:
    # Set the style and font sizes
    sns.set_style('ticks')
    plt.rcParams.update({'font.size': 8})

    # Create a Seaborn line plot with different markers for each product
    sns.lineplot(data=df, x=experiment, y="n_isolates", hue='n_genes', palette='rocket')

    # Set plot title and axes labels
    plt.title(f'Speed of {experiment}')
    plt.xlabel('Time [sec]')
    plt.ylabel('Number of isolates')

    # Add a legend
    plt.legend(loc='lower right', title='Number of genes')

    # Add a grid
    plt.grid(True)

    # Remove the top and right spines
    sns.despine()

    plt.show()

# %% Using STATSMODELS
import statsmodels.api as sm
import statsmodels.formula.api as smf

# %%
df_with_model = df.copy()
for experiment in ['scoary', 'scoary2']:
    print(f'================================= GLM for {experiment} =================================')
    mod = smf.glm(formula=f"{experiment} ~ n_isolates + n_genes", data=df_with_model)  # , groups="subject", )  # cov_struct=ind, family=fam)

    res = mod.fit()

    df_with_model[f'{experiment}_simulated'] = res.params['Intercept'] + (df['n_isolates'] * res.params['n_isolates']) + (df['n_genes'] * res.params['n_genes'])

    print(res.summary())  # pseudo-R²: 0.9972 and 0.9997
    print()

# %%
plot(
    df_with_model,
    x='n_isolates',
    y='n_genes',
    zs=[
        ('scoary', 'darkred', plt.cm.Reds, 0.2),
        ('scoary_simulated', 'lightcoral', plt.cm.Reds, 0.1),
        ('scoary2', 'darkblue', plt.cm.Blues, 0.2),
        ('scoary2_simulated', 'lightskyblue', plt.cm.Blues, 0.1)
    ],
    azim=-80
)

# %%
df_melted = df.melt(id_vars=['n_isolates', 'n_genes'], var_name='scoary_version', value_name='time')
# df_melted['scoary_version'] = df_melted['scoary_version'] == 'scoary2'

# md = smf.mixedlm("time ~ n_isolates + n_genes", data=df_melted, groups=df_melted["scoary_version"])
model = sm.OLS.from_formula('time ~ n_genes * scoary_version + n_isolates * scoary_version', data=df_melted)
results = model.fit()

print(results.summary())  # R² is only 0.663

# %% Using PySR / Symbolic Regression
from pysr import PySRRegressor

model = PySRRegressor(
    niterations=40,  # < Increase me for better results
    binary_operators=["+", "*"],
    unary_operators=[
        "exp",
        "inv(x) = 1/x",
        # ^ Custom operator (julia syntax)
    ],
    extra_sympy_mappings={"inv": lambda x: 1 / x},
    # ^ Define operator for SymPy as well
    loss="L2DistLoss()",  # default
    # loss="loss(prediction, target) = (prediction - target)^2",
    # ^ Custom loss function (julia syntax)
)

# %%
model.fit(df[['n_isolates', 'n_genes']], df['scoary'])
print(model.equations_[['complexity', 'loss', 'score', 'sympy_format']].sort_values('score', ascending=False).to_string())
#     complexity      loss     score                                                                           sympy_format
# 2            5  0.000031  2.116326                                                        2.6693995e-5*n_genes*n_isolates
# 1            3  0.002136  0.305496                                                                0.0014034713*n_isolate
# s
# 3            7  0.000024  0.133921                                          2.8063288e-5*n_genes*(n_isolates - 3.3328335)
# 7           17  0.000015  0.132478                        5.9453797e-8*n_genes*n_isolates*(n_isolates + 368.429747354498)
# 10          20  0.000014  0.030062  5.9453797e-8*n_genes*(n_isolates + 0.573767674698056)*(n_isolates + 368.429747354498)
# 5           12  0.000023  0.022373             2.7807815e-5*n_genes*(n_isolates - 2.938611 + 7.54712880050765/n_isolates)
# 8           18  0.000015  0.017764      5.9453797e-8*n_genes*n_isolates*(0.825404565857421*n_isolates + 384.340179874234)
# 9           19  0.000015  0.015848                        5.9453797e-8*n_genes*n_isolates*(n_isolates + 370.463477354498)
# 6           14  0.000023  0.000782              2.7807815e-5*n_genes*(n_isolates - 2.938611 + 7.9112388204768/n_isolates)
# 4           10  0.000024  0.000290                            2.7807815e-5*n_genes*(n_isolates - 2.938611 + 1/n_isolates)
# 0            1  0.003934  0.000000                                                                     0.0725786300000000
model.fit(df[['n_isolates', 'n_genes']], df['scoary2'])
print(model.equations_[['complexity', 'loss', 'score', 'sympy_format']].sort_values('score', ascending=False).to_string())
#    complexity          loss     score                                                                           sympy_format
# 2           5  2.263219e-07  0.884745                                                         8.678912e-7*n_genes*n_isolates
# 4           8  9.565511e-08  0.664334                                 n_isolates*(7.766743e-7*n_genes + 7.53249666544822e-6)
# 1           3  1.328024e-06  0.469940                                                                4.8942016e-5*n_isolates
# 7          15  7.541305e-08  0.138500    3.4092494448896e-7*n_isolates*(2*n_genes + 0.42849305*n_isolates - 0.5394101899647)
# 3           7  1.858767e-07  0.098437                                  n_isolates*(8.678912e-7*n_genes + 3.0091271997952e-6)
# 9          18  7.007049e-08  0.026405  3.4092494448896e-7*n_isolates*(2*n_genes + 0.42849305*n_isolates + 0.603774049479693)
# 5          10  9.106109e-08  0.024609                   (7.766743e-7*n_genes + 7.53249666544822e-6)*(n_isolates - 1.2873031)
# 8          17  7.194533e-08  0.023537  3.4092494448896e-7*n_isolates*(2*n_genes + 0.42849305*n_isolates + 0.175279534393599)
# 6          14  8.661562e-08  0.012513                                n_isolates*(7.6270385e-7*n_genes + 9.64416732448681e-6)
# 0           1  3.399310e-06  0.000000                                                                    0.00255381480000000


# %%
df_with_model = df.copy()
# scoary: 2.6693995e-5*n_genes*n_isolates
df_with_model[f'scoary_simulated'] = 2.6693995e-5 * df['n_isolates'] * df['n_genes']
# scoary2: 8.678912e-7*n_genes*n_isolates
df_with_model[f'scoary2_simulated'] = 8.678912e-7 * df['n_isolates'] * df['n_genes']

# %%
plot(
    df_with_model,
    x='n_isolates',
    y='n_genes',
    zs=[
        ('scoary', 'darkred', plt.cm.Reds, 0.2),
        ('scoary_simulated', 'lightcoral', plt.cm.Reds, 0.1),
        ('scoary2', 'darkblue', plt.cm.Blues, 0.2),
        ('scoary2_simulated', 'lightskyblue', plt.cm.Blues, 0.1)
    ],
    azim=-80
)

# %%
for azim in range(0, 360, 1):
    print(f'{azim}/360', end='\r')
    plot(
        df_with_model,
        x='n_isolates',
        y='n_genes',
        zs=[
            ('scoary', 'darkred', plt.cm.Reds, 0.2),
            ('scoary_simulated', 'lightcoral', plt.cm.Reds, 0.1),
            ('scoary2', 'darkblue', plt.cm.Blues, 0.2),
            ('scoary2_simulated', 'lightskyblue', plt.cm.Blues, 0.1)
        ],
        azim=azim,
        dpi=80,
        save_path=f'TMP/benchmark2_with_PySR/{azim:03d}.png'
    )
# ffmpeg -i benchmark2_with_PySR/%03d.png -c:v libx264 -r 30 -pix_fmt yuv420p out_pysr.mp4
