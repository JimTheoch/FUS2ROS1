# -*- coding: utf-8 -*-

import adsk, adsk.core, adsk.fusion, traceback
import os
import sys
import re
from .utils import utils
from .core import Link, Joint, Write

# Global reference to avoid early garbage collection
handlers = []
save_dir_global = ""
base_link_target = ""
mesh_quality = "Medium"  # Default quality

class ExporterCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        progress_dialog = None
        ui = None
        try:
            global save_dir_global, base_link_target, mesh_quality
            app = adsk.core.Application.get()
            ui = app.userInterface
            product = app.activeProduct
            design = adsk.fusion.Design.cast(product)
            title = 'Fusion2URDF Exporter'

            # Initialize and launch the progress tracking window
            progress_dialog = ui.createProgressDialog()
            progress_dialog.isBackgroundTranslucent = False
            progress_dialog.isCancelButtonShown = False
            
            progress_dialog.show(
                'URDF EXPORTER RUNNING', 
                'Processing assembly geometries... Please wait.', 
                0, 100, 0
            )
            adsk.doEvents()

            success_msg = 'Successfully create URDF file'
            msg = success_msg
            
            root = design.rootComponent  
            components = design.allComponents

            # Setup directory names        
            robot_name = root.name.split()[0]
            package_name = robot_name + '_description'
            
            final_save_dir = save_dir_global + '/' + package_name
            try: 
                os.mkdir(final_save_dir)
            except: 
                pass     

            package_dir = os.path.abspath(os.path.dirname(__file__)) + '/package/'
            
            progress_dialog.progressValue = 15
            progress_dialog.message = 'Generating assembly and joint configurations...'
            adsk.doEvents()
            
            # --------------------
            # Generate Dictionaries
            joints_dict, msg = Joint.make_joints_dict(root, msg)
            
            # CRITICAL ERROR FIX: Intercept raw "Body_" entries in joints_dict 
            # and re-route them to the selected base link component so Write.py won't KeyError!
            if isinstance(joints_dict, dict):
                for j_name, j_info in list(joints_dict.items()):
                    if j_info.get('parent') == 'Body_1' or 'Body_' in str(j_info.get('parent')):
                        j_info['parent'] = 'base_link'
                    if j_info.get('child') == 'Body_1' or 'Body_' in str(j_info.get('child')):
                        j_info['child'] = 'base_link'

            if msg != success_msg:
                if progress_dialog: progress_dialog.hide()
                ui.messageBox(msg, title)
                return   
            
            inertial_dict, msg = Link.make_inertial_dict(root, msg)
            if msg != success_msg:
                if progress_dialog: progress_dialog.hide()
                ui.messageBox(msg, title)
                return
            
            # DYNAMIC MAP: Anchor our selected dropdown target to 'base_link'
            if base_link_target in inertial_dict:
                inertial_dict['base_link'] = inertial_dict[base_link_target]
            elif not 'base_link' in inertial_dict:
                matched_key = None
                for key in inertial_dict.keys():
                    if base_link_target in key or key in base_link_target:
                        matched_key = key
                        break
                if matched_key:
                    inertial_dict['base_link'] = inertial_dict[matched_key]
                else:
                    if progress_dialog: progress_dialog.hide()
                    msg = f'Target component "{base_link_target}" physical data could not be compiled. Please verify assembly.'
                    ui.messageBox(msg, title)
                    return
            
            links_xyz_dict = {}
            
            progress_dialog.progressValue = 40
            progress_dialog.message = 'Writing URDF, Xacro, and Launch scripts...'
            adsk.doEvents()
            
            # --------------------
            # Write Out URDF & Configuration packages
            Write.write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir)
            Write.write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir)
            Write.write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir)
            Write.write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir)
            Write.write_display_launch(package_name, robot_name, final_save_dir)
            Write.write_gazebo_launch(package_name, robot_name, final_save_dir)
            Write.write_control_launch(package_name, robot_name, final_save_dir, joints_dict)
            Write.write_yaml(package_name, robot_name, final_save_dir, joints_dict)
            
            # Copy templates
            utils.copy_package(final_save_dir, package_dir)
            utils.update_cmakelists(final_save_dir, package_name)
            utils.update_package_xml(final_save_dir, package_name)

            progress_dialog.progressValue = 70
            progress_dialog.message = 'Exporting solid 3D meshes (This can take a few seconds)...'
            adsk.doEvents()

            # Export meshes with selected quality
            utils.export_stl(design, final_save_dir, components, mesh_quality)   
            
            progress_dialog.progressValue = 100
            adsk.doEvents()
            progress_dialog.hide()
            
            ui.messageBox('[SUCCESS] ' + msg, title)
        except:
            if progress_dialog:
                progress_dialog.hide()
            if ui:
                ui.messageBox('[ERROR] Execution Failed:\n{}'.format(traceback.format_exc()))


class ExporterValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global save_dir_global, base_link_target
            if not save_dir_global or not os.path.exists(save_dir_global) or not base_link_target:
                args.areInputsValid = False
                return
                
            args.areInputsValid = True
        except:
            pass


class ExporterCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global base_link_target, mesh_quality
            cmd = args.command
            onExecute = ExporterCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
            
            onInputChanged = ExporterInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            handlers.append(onInputChanged)

            onValidate = ExporterValidateInputsHandler()
            cmd.validateInputs.add(onValidate)
            handlers.append(onValidate)

            inputs = cmd.commandInputs
            
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            root = design.rootComponent
            
            # Base Link Selection Dropdown
            dropdown = inputs.addDropDownCommandInput('base_link_dropdown', '[BASE LINK COMPONENT]', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            dropdown_items = dropdown.listItems
            
            # Gather occurrence names matching the formatting Link.py applies
            for occ in root.occurrences:
                clean_name = re.sub('[ :()]', '_', occ.name)
                is_selected = (clean_name == 'base_link')
                dropdown_items.add(clean_name, is_selected, '')
                
            if dropdown_items.count > 0:
                if not dropdown.selectedItem:
                    dropdown_items.item(0).isSelected = True
                base_link_target = dropdown.selectedItem.name
            
            # Mesh Quality Dropdown - FIXED: add() only takes (name, isSelected)
            mesh_dropdown = inputs.addDropDownCommandInput('mesh_quality_dropdown', '[MESH QUALITY]', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
            mesh_items = mesh_dropdown.listItems
            
            # Add mesh quality options - using (name, isSelected) only
            mesh_items.add('Low (Fastest, Smallest files - Default)', True)
            mesh_items.add('Medium (Balanced)', False)
            mesh_items.add('High (Slower, Larger files)', False)
            
            # Set the default selection
            if mesh_items.count > 0:
                # Find and select Medium
                for i in range(mesh_items.count):
                    if 'Low' in mesh_items.item(i).name:
                        mesh_items.item(i).isSelected = True
                        mesh_quality = 'Low'
                        break
            
            # Export Path Display
            inputs.addTextBoxCommandInput('dir_text_box', '[EXPORT PATH]', 'No output path selected...', 1, True)
            
            # Folder Selection Button
            inputs.addBoolValueInput('select_loc_btn', '>> Select Export Folder <<', False, '', True)
            
            cmd.okButtonText = "Generate Package"
            
        except:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox('Failed to build dialog workspace:\n{}'.format(traceback.format_exc()))


class ExporterInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global save_dir_global, base_link_target, mesh_quality
            app = adsk.core.Application.get()
            ui = app.userInterface
            cmdInput = args.input
            inputs = cmdInput.commandInputs
            
            if cmdInput.id == 'base_link_dropdown':
                if cmdInput.selectedItem:
                    base_link_target = cmdInput.selectedItem.name
            
            elif cmdInput.id == 'mesh_quality_dropdown':
                if cmdInput.selectedItem:
                    # Extract quality from the selected item name
                    selected_text = cmdInput.selectedItem.name
                    if 'Low' in selected_text:
                        mesh_quality = 'Low'
                    elif 'Medium' in selected_text:
                        mesh_quality = 'Medium'
                    elif 'High' in selected_text and 'Very' not in selected_text:
                        mesh_quality = 'High'
                    else:
                        mesh_quality = 'Low'  # Default fallback
            
            elif cmdInput.id == 'select_loc_btn':
                folder_chosen = utils.file_dialog(ui)
                if folder_chosen:
                    save_dir_global = folder_chosen
                    path_display = inputs.itemById('dir_text_box')
                    if path_display:
                        path_display.text = save_dir_global
        except:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox('Input change handler failure:\n{}'.format(traceback.format_exc()))


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        global save_dir_global, base_link_target, mesh_quality
        save_dir_global = "" 
        base_link_target = ""
        mesh_quality = "Medium"  # Default to Medium

        cmd_def = ui.commandDefinitions.itemById('URDF_Exporter_GUI_Cmd')
        if cmd_def:
            cmd_def.deleteMe()
            
        cmd_def = ui.commandDefinitions.addButtonDefinition('URDF_Exporter_GUI_Cmd', 'ROS URDF Configuration Panel', 'Configure generation paths, root tracking, and mesh quality settings.')
        
        onCreated = ExporterCommandCreatedHandler()
        cmd_def.commandCreated.add(onCreated)
        handlers.append(onCreated)
        
        cmd_def.execute()
        adsk.autoTerminate(False)
        
    except:
        if ui:
            ui.messageBox('Initialization Engine Failed:\n{}'.format(traceback.format_exc()))
