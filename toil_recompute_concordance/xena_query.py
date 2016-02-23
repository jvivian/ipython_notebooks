"""
Utilities for xena queries.

A basic query example.
Queries are scheme expressions.

>>> import xena_query as xena
>>> xena.post("https://genome-cancer.ucsc.edu/proj/public/xena", "(+ 1 2)")
'3.0'

>>> xena.post("https://genome-cancer.ucsc.edu/proj/public/xena", "(let [x 2 y (+ x 3)] (* x y))")
'10.0'

Find all the identifiers of a dataset
>>> probes = xena.dataset_field("https://genome-cancer.ucsc.edu/proj/public/xena", "public/TCGA/TCGA.PANCAN.sampleMap/HiSeqV2")
>>> print probes[-10:]
'[u'ZXDB', u'ZXDC', u'ZYG11A', u'ZYG11B', u'ZYX', u'ZZEF1', u'ZZZ3', u'psiTPTE22', u'sampleID', u'tAKR']'

Find all the samples of a dataset
>>> samples = xena.dataset_samples("https://genome-cancer.ucsc.edu/proj/public/xena", "public/TCGA/TCGA.PANCAN.sampleMap/HiSeqV2")
>>> print samples[:5]
'[u'TCGA-S9-A7J2-01', u'TCGA-G3-A3CH-11', u'TCGA-EK-A2RE-01', u'TCGA-44-6778-01', u'TCGA-VM-A8C8-01']'

Find value matrix of a particular set of samples and identifiers (genes, probes, isoforms)
>>> values = xena.dataset_probe_values("https://genome-cancer.ucsc.edu/proj/public/xena", "public/TCGA/TCGA.PANCAN.sampleMap/HiSeqV2",["TCGA-44-6778-01","TCGA-44-6778-01"],["TP53"])
>>> print values
[[10.4169, 10.4169]]


Looking up sample ids for the TCGA LGG cohort.

>>> r = xena.post("https://genome-cancer.ucsc.edu/proj/public/xena",
                  xena.patient_to_sample_query("TCGA.LGG.sampleMap",
                                               ["TCGA-CS-4938",
                                                "TCGA-HT-7693",
                                                "TCGA-CS-6665",
                                                "TCGA-S9-A7J2",
                                                "TCGA-FG-A6J3"]))
'{"TCGA.LGG.sampleMap":["TCGA-CS-4938-01","TCGA-CS-6665-01","TCGA-FG-A6J3-01","TCGA-HT-7693-01","TCGA-S9-A7J2-01"]}'

>>> r = xena.post("https://genome-cancer.ucsc.edu/proj/public/xena",
                  xena.find_sample_by_field_query("TCGA.LGG.sampleMap",
                                                    "_PATIENT",
                                                    ["TCGA-CS-4938",
                                                     "TCGA-HT-7693",
                                                     "TCGA-CS-6665",
                                                     "TCGA-S9-A7J2",
                                                     "TCGA-FG-A6J3"]))
'{"TCGA.LGG.sampleMap":["TCGA-CS-4938-01","TCGA-CS-6665-01","TCGA-FG-A6J3-01","TCGA-HT-7693-01","TCGA-S9-A7J2-01"]}'
>>> import json
>>> json.loads(r)
{u'TCGA.LGG.sampleMap': [u'TCGA-CS-4938-01', u'TCGA-CS-6665-01', u'TCGA-FG-A6J3-01', u'TCGA-HT-7693-01', u'TCGA-S9-A7J2-01']}
"""

import urllib2, json
import re

def compose1(f, g):
    def composed(*args, **kwargs):
        return f(g(*args, **kwargs))
    return composed

# funcitonal composition, e.g.
# compose(f, g)(a, ...) == f(g(a, ...))
compose = lambda *funcs: reduce(compose1, funcs)

def quote(s):
    return '"' + s + '"'

def array_fmt(l):
    return '[' + ', '.join((quote(s) for s in l)) + ']'

# The strategy here is
#   o Do table scan on code to find codes matching field values
#   o Do IN query on unpack(field, x) to find rows matching codes
#   o Project to unpack(sample, x) to get sampleID code
#   o Join with code to get sampleID values
#
# Note the :limit on the table scan. This makes the table scan exit after we've
# found enough values, rather than continuing to the end. We can do this because
# enumerated values are unique. An alternative would be to index all the enumerated
# values in the db.

cohort_query_str = """
(map :cohort (query {:select [:%distinct.cohort]
                     :from [:dataset]
                     :where [:not [:is nil :cohort]]}))
"""

datasets_list_in_cohort_str ="""
(map :name (query {:select [:name :type :datasubtype :probemap :text :status]
      :from [:dataset]
      :where [:= :cohort %s]}))
"""

dataset_type_str = """
(map :type (query {:select [:type]
                   :from [:dataset]
                   :where [:= :name %s]}))
"""

dataset_field_str = """
(map :name (query {:select [:field.name]
             :from [:dataset]
             :join [:field [:= :dataset.id :dataset_id]]
             :where [:= :dataset.name %s]}))
"""

dataset_samples_str = """
(map :value (query {:select [:value]
            :from [:dataset]
            :join [:field [:= :dataset.id :dataset_id]
            :code [:= :field.id :field_id]]
            :where [:and
            [:= :dataset.name %s]
            [:= :field.name "sampleID"]]}))
"""

dataset_probe_str = """
    (fetch [{:table %s
          :columns %s
          :samples %s}])
"""


def find_sample_by_field_query(cohort, field, values):
    """Return a xena query which looks up sample ids for the given field=values."""
    return sample_query_str % (quote(cohort), quote(field), array_fmt(values))

def patient_to_sample_query(cohort, patients):
    """Return a xena query which looks up sample ids for the given patients."""
    return find_sample_by_field_query(cohort, "_PATIENT", patients)

headers = { 'Content-Type' : "text/plain" }

def post(url, query):
    """POST a xena data query to the given url."""
    req = urllib2.Request(url + '/data/', query, headers)
    response = urllib2.urlopen(req)
    result = response.read()
    return result

def find_cohorts(url):
    """ Return a list of cohorts on a host at a specific url """
    """ return example: ["chinSF2007_public","TCGA.BRCA.sampleMap","cohort3"] """
    return json.loads(post(url,cohort_query_str))

def dataset_field(host, dataset):
    """return probes or features of a dataset"""
    return json.loads(post(host, dataset_field_str % (quote(dataset))))

def datasets_list_in_cohort (host, cohort):
    """return datasets in a cohort"""
    return json.loads(post(host, datasets_list_in_cohort_str % (quote(cohort))))

def dataset_samples (host, dataset):
    return json.loads(post(host, dataset_samples_str % (quote(dataset))))

def dataset_probe_values (host, dataset, samples, probes):
    """ return matrix of values [[x11, x12, ...],[x21, x22,...],...]"""
    """ x11: sample 1 and probe 1"""
    """ x12: sample 2 and probe 1"""
    """ x21: sample 1 and probe 2"""
    """ x22: sample 2 and probe 2"""
    return json.loads(post(host, dataset_probe_str % (quote(dataset), array_fmt(probes), array_fmt(samples))))

def dataset_type (host, dataset):
    return json.loads(post(host, dataset_type_str % (quote(dataset))))

def strip_first_url_dir(path):
    return re.sub(r'^[^/]*', '', path)

# proj/<proj>/xena/<proj>/<path>
# download/<proj>/xena/<path>
def name_to_url(base_url, name):
    return base_url.replace('/proj/', '/download/') + strip_first_url_dir(name)

