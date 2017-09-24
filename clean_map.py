import xml.etree.cElementTree as ET
import pprint
from collections import defaultdict
import re
import csv
import codecs
from collections import OrderedDict
#import cerberus
#import schema


OSM_PATH = "C:/Users/layal/Desktop/Data Wrangling Proj/map"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

street_types = defaultdict(set)
district_types = defaultdict(set)

node_attribs = {}
way_attribs = {}
way_nodes = []
tags = []  # Handle secondary tags the same way for both node and way elements
corrected_street_names = {}
way_tag_types = defaultdict(int)
node_tag_types = defaultdict(int)

NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']
    
lower = re.compile(r'^([a-z]|_)*$')
LOWER_COLON = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

#SCHEMA = schema.schema

street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)
expected_street_types = ["Street", "Avenue", "Boulevard", "Road", "Drive",\
                         "Court", "Circle", "Lane", "Garden", "Place"]
expected_district_types = ["NW", "NE", "SW", "SE"]

street_mapping = { "St": "Street",
            "St.": "Street",
            "Ave" : "Avenue",
            "Rd." : "Road",
            "Blvd" : "Boulovard",
            "Pl" : "Plaza",
            "St" : "Street"           
            }

district_mapping = { "N": "NW",
            "N.E.": "NE",
            "North" : "NW",
            "Northwest" : "NW",
            "South" : "SW",
            "West" : "NW",
            "NW" : "NW",
            "NE" : "NE",
            "SW" : "SW",
            "SE" : "SE"
            }

def count_tags(filename):
    mytags = defaultdict(int)
    myfile = open(filename, "r")
    for event, element in ET.iterparse(myfile, events = ("start",)):
        mytags[element.tag] +=1
        
    return mytags


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements
    tag_id = 0
    
    for attribName, attribValue in element.items():
        if element.tag == "node":
            if attribName in node_attr_fields:
                node_attribs[attribName] = attribValue
        elif element.tag == "way" and attribName in way_attr_fields:
            way_attribs[attribName] = attribValue
        if attribName == "id":
            tag_id = attribValue
        
    for atag in element.findall("./tag"):
        newdict = {}

        tag_type = default_tag_type
        if atag.attrib["k"] and PROBLEMCHARS.search(atag.attrib["k"]):
            continue
        elif atag.attrib["k"] and LOWER_COLON.search(atag.attrib["k"]):
            tag_type = atag.attrib["k"].split(":", 1)[0]
            tag_key = atag.attrib["k"].split(":", 1)[1]
        elif atag.attrib["k"]:
            tag_key = atag.attrib["k"]
        tag_value = atag.attrib["v"]
        if tag_key == "street" and element.tag == "way":
            try:
                tag_value = corrected_street_names[tag_value]
            except KeyError:
                print tag_value

        newdict["id"] = tag_id
        newdict["key"] = tag_key
        newdict["type"] = tag_type
        newdict["value"] = tag_value
        tags.append(newdict)
        
    if element.tag == "way":
        count = 0
        for atag in element.findall('./nd'):
            mydict = OrderedDict()
            mydict["id"] = id
            mydict["node_id"] = atag.attrib["ref"]
            mydict["position"] = count
            way_nodes.append(mydict)
            count += 1
            
    
    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}



def audit_street_types(street_types, street_name):
    street_name = street_name.rsplit(" ", 1)[0]
    m = street_type_re.search(street_name)
    if m:# if this is true then there is a match of somekind
        street_type = m.group()
        if street_type not in expected_street_types:
            street_types[street_type].add(street_name)
            
def audit_district_types(district_types, district_name):
    district_name = district_name.rsplit(" ", 1)[1]
    m = street_type_re.search(district_name)
    if m:# if this is true then there is a match of somekind
        district_type = m.group()
        if district_type not in expected_district_types:
            district_types[district_type].add(district_name)

def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

def fix_street_types(street_name):
    if street_name in corrected_street_names.keys():
        return corrected_street_names[street_name]
    original_street_name = street_name
    street_breakdown = street_name.rsplit(" ", 2)
    district_type = street_breakdown[-1]
    street_type = street_breakdown[-2]
    street_name = street_breakdown[0]

    #assert street_type in street_types.keys()
    #assert district_type in district_types.keys()
    correct =  street_name + " " + \
    (street_mapping[street_type] if street_type in street_mapping else street_type) + " " + \
    (district_mapping[district_type] if district_type in district_mapping else district_type)
    corrected_street_names[original_street_name] = correct


# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

'''
def validate_element(element, validator, schema=SCHEMA):
    
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))
'''
class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])

def process_way(element):
        
    assert(element.tag == "way")

    for tag in element.iter("tag"):
        if is_street_name(tag):
            audit_street_types(street_types, tag.attrib['v'])
            audit_district_types(district_types, tag.attrib['v'])
            fix_street_types(tag.attrib['v'])


def process_node(element, node_attr_fields=NODE_FIELDS,
                default_tag_type='regular'):
    return
    
def audit(file_in):

    myfile = open(file_in, 'r')
    for event, element in ET.iterparse(myfile, events=("start",)):
        if element.tag == "way":
            process_way(element)
        elif element.tag == "node":
            process_node(element)
    myfile.close()
    
#    with open("way_tag_types", "wb") as f:
#        for key, value in way_tag_types.items():
#            f.write(str(key)+"\t"+str(value)+"\n")
        
#    f.close()
    #pprint.pprint(dict(way_tag_types))
    
    #return street_types

if __name__ == "__main__":
    audit(OSM_PATH)
    process_map(OSM_PATH, validate=True)