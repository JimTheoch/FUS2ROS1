# -*- coding: utf-8 -*-
"""
Created on Sun May 12 19:15:34 2019

@author: syuntoku
"""

import adsk, adsk.core, adsk.fusion
import os.path, re
from xml.etree import ElementTree
from xml.dom import minidom
import shutil
import fileinput
import sys

def clean_name(name):
    """Replace spaces and special characters with underscores"""
    return re.sub('[ :()]', '_', name)

def format_name(name):
    """Format name for ROS (replace spaces and special chars)"""
    return re.sub('[ :()]', '_', name)

def convert_german(name):
    """Convert German umlauts to ASCII"""
    # Replace German umlauts
    name = name.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
    name = name.replace('Ä', 'Ae').replace('Ö', 'Oe').replace('Ü', 'Ue')
    name = name.replace('ß', 'ss')
    return name

def get_material_from_occurrence(occ):
    """
    Extract material/color from a Fusion occurrence
    
    Parameters
    ----------
    occ: adsk.fusion.Occurrence
        The occurrence to get material from
        
    Returns
    -------
    tuple: (material_name, color_rgba_string)
    """
    appearance = None
    
    # Try to get appearance from the occurrence
    if hasattr(occ, 'appearance') and occ.appearance:
        appearance = occ.appearance
    # Try to get from bodies
    elif hasattr(occ, 'bRepBodies') and occ.bRepBodies:
        for body in occ.bRepBodies:
            if body.appearance:
                appearance = body.appearance
                break
    # Try to get from component material
    elif hasattr(occ, 'component') and occ.component:
        if hasattr(occ.component, 'material') and occ.component.material:
            appearance = occ.component.material.appearance
    
    if appearance:
        for prop in appearance.appearanceProperties:
            if type(prop) == adsk.core.ColorProperty:
                prop_name = appearance.name
                color_name = format_name(convert_german(prop_name))
                if not color_name:
                    color_name = "silver"
                color_rgba = f"{prop.value.red/255:.3f} {prop.value.green/255:.3f} {prop.value.blue/255:.3f} {prop.value.opacity/255:.3f}"
                return color_name, color_rgba
    
    return "silver", "0.700 0.700 0.700 1.000"

# utils.py - Modified copy_occs function

def copy_occs(root):    
    """duplicate all the components without renaming originals"""
    def copy_body(allOccs, occs):
        """copy the old occs to new component"""
        bodies = occs.bRepBodies
        transform = adsk.core.Matrix3D.create()
        
        # Create a new component
        new_occs = allOccs.addNewComponent(transform)
        
        # Name the new component
        if occs.component.name == 'base_link':
            new_occs.component.name = 'base_link'
        else:
            new_occs.component.name = re.sub('[ :()]', '_', occs.name)
        
        # Get reference to the newly created component
        new_occs_ref = allOccs.item((allOccs.count-1))
        
        # Copy all bodies to the new component
        for i in range(bodies.count):
            body = bodies.item(i)
            body.copyToComponent(new_occs_ref)
        
        # Rename the original component to 'old_component'
        # This prevents double STL export
        original_name = occs.component.name
        if original_name != 'old_component':
            occs.component.name = 'old_component'
    
    allOccs = root.occurrences
    
    # Only process occurrences that have bodies and are not already old_component
    coppy_list = [occs for occs in allOccs if occs.bRepBodies.count > 0 and occs.component.name != 'old_component']
    
    for occs in coppy_list:
        copy_body(allOccs, occs)
def export_stl(design, save_dir, components, quality="Medium", base_link_name=None):  
    """
    export stl files into save_dir/
    
    Parameters
    ----------
    design: adsk.fusion.Design.cast(product)
    save_dir: str
        directory path to save
    components: design.allComponents
    quality: str
        Mesh quality setting: 'Low', 'Medium', 'High'
    base_link_name: str
        Name of the component to export as base_link.stl (if None, uses original name)
    """
    exportMgr = design.exportManager
    try:
        os.mkdir(save_dir + '/meshes')
    except:
        pass
    scriptDir = save_dir + '/meshes'
    
    # Map quality strings to Fusion 360 MeshRefinement settings
    quality_map = {
        'Low': adsk.fusion.MeshRefinementSettings.MeshRefinementLow,
        'Medium': adsk.fusion.MeshRefinementSettings.MeshRefinementMedium,
        'High': adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    }
    
    # Default to Medium if quality not found
    mesh_refinement = quality_map.get(quality, adsk.fusion.MeshRefinementSettings.MeshRefinementMedium)
    
    for component in components:
        allOccus = component.allOccurrences
        for occ in allOccus:
            if 'old_component' not in occ.component.name:
                try:
                    # Determine the filename
                    # If this is the base_link component, export as base_link.stl
                    if base_link_name and occ.component.name == base_link_name:
                        fileName = scriptDir + "/base_link"
                    else:
                        fileName = scriptDir + "/" + occ.component.name
                    
                    stlExportOptions = exportMgr.createSTLExportOptions(occ, fileName)
                    stlExportOptions.sendToPrintUtility = False
                    stlExportOptions.isBinaryFormat = True
                    stlExportOptions.meshRefinement = mesh_refinement
                    exportMgr.execute(stlExportOptions)
                    print(f'Exported: {occ.component.name} -> {fileName}.stl')
                except Exception as e:
                    print('Component ' + occ.component.name + ' has something wrong: ' + str(e))


def file_dialog(ui):     
    """display the dialog to save the file"""
    folderDlg = ui.createFolderDialog()
    folderDlg.title = 'Fusion Folder Dialog' 
    dlgResult = folderDlg.showDialog()
    if dlgResult == adsk.core.DialogResults.DialogOK:
        return folderDlg.folder
    return False


def origin2center_of_mass(inertia, center_of_mass, mass):
    """convert the moment of the inertia about the world coordinate into 
    that about center of mass coordinate"""
    x = center_of_mass[0]
    y = center_of_mass[1]
    z = center_of_mass[2]
    translation_matrix = [y**2 + z**2, x**2 + z**2, x**2 + y**2,
                         -x*y, -y*z, -x*z]
    return [round(i - mass*t, 6) for i, t in zip(inertia, translation_matrix)]


def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def copy_package(save_dir, package_dir):
    """Copy package files to the save directory"""
    try:
        if not os.path.exists(save_dir + '/launch'):
            os.mkdir(save_dir + '/launch')
        if not os.path.exists(save_dir + '/urdf'):
            os.mkdir(save_dir + '/urdf')
        
        if os.path.exists(package_dir):
            shutil.copytree(package_dir, save_dir, dirs_exist_ok=True)
        else:
            print(f"Package directory '{package_dir}' does not exist.")
        
    except Exception as e:
        print(f"Error copying package: {e}")


def update_cmakelists(save_dir, package_name):
    """Update CMakeLists.txt with the package name"""
    file_name = save_dir + '/CMakeLists.txt'
    if not os.path.exists(file_name):
        with open(file_name, 'w') as f:
            f.write('cmake_minimum_required(VERSION 2.8.3)\n')
            f.write(f'project({package_name})\n\n')
            f.write('find_package(catkin REQUIRED COMPONENTS\n')
            f.write('  roscpp\n')
            f.write('  rospy\n')
            f.write('  std_msgs\n')
            f.write(')\n\n')
            f.write('catkin_package()\n')
        return
    
    with open(file_name, 'r') as f:
        content = f.read()
    
    content = content.replace('%RobName%', package_name)
    
    with open(file_name, 'w') as f:
        f.write(content)


def update_package_xml(save_dir, package_name):
    """Update package.xml with the package name"""
    file_name = save_dir + '/package.xml'
    if not os.path.exists(file_name):
        with open(file_name, 'w') as f:
            f.write('<?xml version="1.0"?>\n')
            f.write('<package format="2">\n')
            f.write(f'  <name>{package_name}</name>\n')
            f.write(f'  <description>The {package_name} package</description>\n')
            f.write('  <version>0.0.0</version>\n')
            f.write('  <maintainer email="user@example.com">user</maintainer>\n')
            f.write('  <license>BSD</license>\n')
            f.write('</package>\n')
        return
    
    with open(file_name, 'r') as f:
        content = f.read()
    
    content = content.replace('%RobName%', package_name)
    
    with open(file_name, 'w') as f:
        f.write(content)