# -*- coding: utf-8 -*-


import adsk, adsk.core, adsk.fusion
import os.path, re
from xml.etree import ElementTree
from xml.dom import minidom
import shutil
import fileinput
import sys

def export_stl(design, save_dir, components, quality="Medium"):  
    """
    export stl files into "save_dir/" without creating duplicate components
    
    Parameters
    ----------
    design: adsk.fusion.Design.cast(product)
    save_dir: str
        directory path to save
    components: design.allComponents
    quality: str
        Mesh quality setting: 'Low', 'Medium', 'High'
    """
          
    # Create a single exportManager instance
    exportMgr = design.exportManager
    # Get the script location
    try: os.mkdir(save_dir + '/meshes')
    except: pass
    scriptDir = save_dir + '/meshes'
    
    # Map quality strings to Fusion 360 MeshRefinement settings
    # NOTE: Fusion 360 only supports Low, Medium, and High
    quality_map = {
        'Low': adsk.fusion.MeshRefinementSettings.MeshRefinementLow,
        'Medium': adsk.fusion.MeshRefinementSettings.MeshRefinementMedium,
        'High': adsk.fusion.MeshRefinementSettings.MeshRefinementHigh,
        'VeryHigh': adsk.fusion.MeshRefinementSettings.MeshRefinementHigh  # Map VeryHigh to High
    }
    
    # Default to Medium if quality not found
    mesh_refinement = quality_map.get(quality, adsk.fusion.MeshRefinementSettings.MeshRefinementMedium)
    
    # Get all occurrences from root component
    root = design.rootComponent
    allOccurrences = root.occurrences
    
    # Export each occurrence directly without copying
    for occ in allOccurrences:
        # Skip if it's an old_component (just in case)
        if 'old_component' in occ.component.name:
            continue
            
        try:
            # Use the occurrence name for the filename
            occ_name = re.sub('[ :()]', '_', occ.name)
            fileName = scriptDir + "/" + occ_name
            
            # Create STL export options directly from the occurrence
            stlExportOptions = exportMgr.createSTLExportOptions(occ, fileName)
            stlExportOptions.sendToPrintUtility = False
            stlExportOptions.isBinaryFormat = True
            stlExportOptions.meshRefinement = mesh_refinement
            
            exportMgr.execute(stlExportOptions)
            print('Exported: ' + occ_name + ' (Quality: ' + quality + ')')
            
        except Exception as e:
            print('Failed to export ' + occ.name + ': ' + str(e))
            # Try exporting the component directly as fallback
            try:
                component = occ.component
                fileName = scriptDir + "/" + re.sub('[ :()]', '_', component.name)
                stlExportOptions = exportMgr.createSTLExportOptions(component, fileName)
                stlExportOptions.sendToPrintUtility = False
                stlExportOptions.isBinaryFormat = True
                stlExportOptions.meshRefinement = mesh_refinement
                exportMgr.execute(stlExportOptions)
                print('Exported component: ' + component.name + ' (Quality: ' + quality + ')')
            except:
                print('Could not export ' + occ.name)


def file_dialog(ui):     
    """
    display the dialog to save the file
    """
    # Set styles of folder dialog.
    folderDlg = ui.createFolderDialog()
    folderDlg.title = 'Fusion Folder Dialog' 
    
    # Show folder dialog
    dlgResult = folderDlg.showDialog()
    if dlgResult == adsk.core.DialogResults.DialogOK:
        return folderDlg.folder
    return False


def origin2center_of_mass(inertia, center_of_mass, mass):
    """
    convert the moment of the inertia about the world coordinate into 
    that about center of mass coordinate

    Parameters
    ----------
    moment of inertia about the world coordinate:  [xx, yy, zz, xy, yz, xz]
    center_of_mass: [x, y, z]
    
    Returns
    ----------
    moment of inertia about center of mass : [xx, yy, zz, xy, yz, xz]
    """
    x = center_of_mass[0]
    y = center_of_mass[1]
    z = center_of_mass[2]
    translation_matrix = [y**2 + z**2, x**2 + z**2, x**2 + y**2,
                         -x*y, -y*z, -x*z]
    return [round(i - mass*t, 6) for i, t in zip(inertia, translation_matrix)]


def prettify(elem):
    """
    Return a pretty-printed XML string for the Element.
    
    Parameters
    ----------
    elem : xml.etree.ElementTree.Element
    
    Returns
    ----------
    pretified xml : str
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def copy_package(save_dir, package_dir):
    try:
        # Check if the target directory exists, if not, create it
        if not os.path.exists(save_dir + '/launch'):
            os.mkdir(save_dir + '/launch')
        if not os.path.exists(save_dir + '/urdf'):
            os.mkdir(save_dir + '/urdf')
        
        # Check if the package directory exists and copy it
        if os.path.exists(package_dir):
            shutil.copytree(package_dir, save_dir, dirs_exist_ok=True)
        else:
            print(f"Package directory '{package_dir}' does not exist.")
        
    except Exception as e:
        print(f"Error copying package: {e}")


def update_cmakelists(save_dir, package_name):
    file_name = save_dir + '/CMakeLists.txt'

    for line in fileinput.input(file_name, inplace=True):
        if 'project(%RobName%_description)' in line:
            sys.stdout.write("project(" + package_name + ")\n")
        else:
            sys.stdout.write(line)


def update_package_xml(save_dir, package_name):
    file_name = save_dir + '/package.xml'

    for line in fileinput.input(file_name, inplace=True):
        if '<name>' in line:
            sys.stdout.write("  <name>" + package_name + "</name>\n")
        elif '<description>' in line:
            sys.stdout.write("<description>The " + package_name + " package</description>\n")
        else:
            sys.stdout.write(line)
