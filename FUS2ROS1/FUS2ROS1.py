#Author-syuntoku14
#Description-Generate URDF file from Fusion 360

import adsk, adsk.core, adsk.fusion, traceback
import os
import sys
import re
from .utils import utils
from .core import Link, Joint, Write

"""
# length unit is 'cm' and inertial unit is 'kg/cm^2'
# If there is no 'body' in the root component, maybe the corrdinates are wrong.
"""

# joint effort: 100
# joint velocity: 100
# supports "Revolute", "Rigid" and "Slider" joint types

# I'm not sure how prismatic joint acts if there is no limit in fusion model

# Global reference to avoid early garbage collection
handlers = []
save_dir_global = ""
mesh_quality = "Medium"
base_link_component = ""

def clean_name(name):
    return re.sub('[ :()]', '_', name)

def extract_materials_from_components(root, base_link_component):
    """
    Extract material/color information from all components
    
    Returns
    -------
    tuple: (material_dict, color_dict)
        material_dict: maps link names to material names
        color_dict: maps material names to RGBA strings
    """
    material_dict = {}
    color_dict = {'silver': '0.700 0.700 0.700 1.000'}
    
    # Process all occurrences
    for occ in root.occurrences:
        occ_name = re.sub('[ :()]', '_', occ.name)
        
        # Handle base_link
        if occ.component.name == 'base_link' or occ_name == base_link_component:
            mat_name, mat_color = utils.get_material_from_occurrence(occ)
            material_dict['base_link'] = mat_name
            color_dict[mat_name] = mat_color
        else:
            mat_name, mat_color = utils.get_material_from_occurrence(occ)
            material_dict[occ_name] = mat_name
            color_dict[mat_name] = mat_color
    
    return material_dict, color_dict

def get_joint_preview(root, base_link_name=None):
    """
    Generate joint preview data for the UI
    
    Parameters
    ----------
    root: adsk.fusion.Component
        Root component
    base_link_name: str
        Name of the base link component
        
    Returns
    -------
    tuple: (stats_text, tree_text, joints_dict)
        stats_text: Formatted statistics string
        tree_text: Formatted tree view string
        joints_dict: The joints dictionary for further use
    """
    try:
        # If no base link selected, show waiting message
        if not base_link_name or base_link_name == "None" or base_link_name == "+++ Select Base Component +++":
            return "⏳ Select a base component to preview", "Waiting for selection...", {}
        
        # Get joints dictionary using existing function
        success_msg = 'Successfully created URDF file'
        joints_dict, msg = Joint.make_joints_dict(root, success_msg)
        
        if msg != success_msg:
            return "❌ Error: " + msg, "No joints available", {}
        
        # Apply base_link renaming if needed
        if base_link_name and joints_dict:
            for joint_name, joint_info in joints_dict.items():
                if joint_info.get('parent') == base_link_name:
                    joint_info['parent'] = 'base_link'
                if joint_info.get('child') == base_link_name:
                    joint_info['child'] = 'base_link'
        
        # Count joint types
        type_counts = {
            'fixed': 0,
            'revolute': 0,
            'prismatic': 0,
            'continuous': 0,
            'other': 0
        }
        
        joint_type_icons = {
            'fixed': '📌',
            'revolute': '🔄',
            'prismatic': '⬛',
            'continuous': '♾️',
            'other': '🔗'
        }
        
        for joint in joints_dict.values():
            jtype = joint['type']
            if jtype in type_counts:
                type_counts[jtype] += 1
            else:
                type_counts['other'] += 1
        
        total_joints = sum(type_counts.values())
        
        # Build statistics text
        stats_lines = []
        stats_lines.append(f"🔗 Total Joints: {total_joints}")
        
        # Show each type with icon on same line
        type_parts = []
        for jtype, count in type_counts.items():
            if count > 0:
                icon = joint_type_icons.get(jtype, '🔗')
                display_name = jtype.capitalize()
                type_parts.append(f"{icon} {display_name}: {count}")
        
        if type_parts:
            stats_lines.append("  " + "  •  ".join(type_parts))
        else:
            stats_lines.append("  No joints found")
        
        stats_text = "\n".join(stats_lines)
        
        # Build tree view
        tree_lines = []
        
        if not joints_dict:
            tree_lines.append("No joints found in the assembly.")
            return stats_text, "\n".join(tree_lines), joints_dict
        
        # Group joints by parent
        parent_groups = {}
        for joint_name, joint_info in joints_dict.items():
            parent = joint_info['parent']
            if parent not in parent_groups:
                parent_groups[parent] = []
            parent_groups[parent].append((joint_name, joint_info))
        
        # Build tree with indentation - clean format
        for parent, children in sorted(parent_groups.items()):
            parent_display = "📁 " + parent if parent == 'base_link' else "📂 " + parent
            tree_lines.append(parent_display)
            
            for joint_name, joint_info in sorted(children, key=lambda x: x[0]):
                jtype = joint_info['type']
                child = joint_info['child']
                icon = joint_type_icons.get(jtype, '🔗')
                display_type = jtype.capitalize()
                
                # Check for potential issues
                warning = ""
                if jtype in ['revolute', 'prismatic']:
                    if joint_info.get('upper_limit', 0) == 0 and joint_info.get('lower_limit', 0) == 0:
                        warning = " ⚠️"
                
                tree_lines.append(f"  ├── {icon} {joint_name} [{display_type}] → {child}{warning}")
        
        tree_text = "\n".join(tree_lines)
        
        return stats_text, tree_text, joints_dict
        
    except Exception as e:
        error_msg = f"❌ Error generating preview: {str(e)}"
        return error_msg, "No joints available", {}

class ExporterCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        progress_dialog = None
        ui = None
        try:
            global save_dir_global, mesh_quality, base_link_component
            app = adsk.core.Application.get()
            ui = app.userInterface
            product = app.activeProduct
            design = adsk.fusion.Design.cast(product)
            title = '🤖 Fusion2URDF'

            if not design:
                ui.messageBox('❌ No active Fusion design found. Please open a design first.', title)
                return

            progress_dialog = ui.createProgressDialog()
            progress_dialog.isBackgroundTranslucent = False
            progress_dialog.isCancelButtonShown = False
            
            progress_dialog.show(
                '⚙️ URDF EXPORTER RUNNING', 
                '⏳ Processing assembly geometries... Please wait.', 
                0, 100, 0
            )
            adsk.doEvents()

            success_msg = '🎉 Successfully created URDF package!'
            msg = success_msg
            
            root = design.rootComponent  
            components = design.allComponents

            raw_robot_name = root.name.split()[0]
            robot_name = clean_name(raw_robot_name)
            
            # Check if the robot name already ends with _description
            if robot_name.endswith('_description'):
                package_name = robot_name
            else:
                package_name = robot_name + '_description'
            
            final_save_dir = save_dir_global + '/' + package_name
            try: 
                os.mkdir(final_save_dir)
            except: 
                pass     

            package_dir = os.path.abspath(os.path.dirname(__file__)) + '/package/'
            
            progress_dialog.progressValue = 15
            progress_dialog.message = '🔗 Generating assembly and joint configurations...'
            adsk.doEvents()
            
            joints_dict, msg = Joint.make_joints_dict(root, msg)
            if msg != success_msg:
                if progress_dialog: progress_dialog.hide()
                ui.messageBox(f'❌ {msg}', title)
                return   
            
            # Check if base_link_component is valid (not None or placeholder)
            if base_link_component and base_link_component not in ["None", "+++ Select Base Component +++"]:
                if joints_dict:
                    for joint_name, joint_info in joints_dict.items():
                        if joint_info.get('parent') == base_link_component:
                            joint_info['parent'] = 'base_link'
                        if joint_info.get('child') == base_link_component:
                            joint_info['child'] = 'base_link'
            else:
                # No valid base component selected
                if progress_dialog: progress_dialog.hide()
                ui.messageBox('❌ Please select a valid base component before exporting.', title)
                return
            
            inertial_dict, msg = Link.make_inertial_dict(root, msg)
            if msg != success_msg:
                if progress_dialog: progress_dialog.hide()
                ui.messageBox(f'❌ {msg}', title)
                return
            
            if base_link_component and base_link_component in inertial_dict:
                inertial_dict['base_link'] = inertial_dict[base_link_component]
            elif not 'base_link' in inertial_dict:
                msg = f'⚠️ Selected component "{base_link_component}" not found in inertial data. Please verify assembly.'
                if progress_dialog: progress_dialog.hide()
                ui.messageBox(msg, title)
                return
            
            # Extract materials from components
            material_dict, color_dict = extract_materials_from_components(root, base_link_component)
            
            links_xyz_dict = {}
            
            progress_dialog.progressValue = 40
            progress_dialog.message = '📄 Writing URDF, Xacro, and Launch scripts...'
            adsk.doEvents()
            
            Write.write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir, material_dict)
            Write.write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir, color_dict)
            Write.write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir)
            Write.write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, final_save_dir, material_dict)
            Write.write_display_launch(package_name, robot_name, final_save_dir)
            Write.write_gazebo_launch(package_name, robot_name, final_save_dir)
            Write.write_control_launch(package_name, robot_name, final_save_dir, joints_dict)
            Write.write_yaml(package_name, robot_name, final_save_dir, joints_dict)
            
            utils.copy_package(final_save_dir, package_dir)
            utils.update_cmakelists(final_save_dir, package_name)
            utils.update_package_xml(final_save_dir, package_name)

            progress_dialog.progressValue = 70
            progress_dialog.message = '🔮 Exporting solid 3D meshes (This can take a few seconds)...'
            adsk.doEvents()

            original_base_link_name = base_link_component
            utils.copy_occs(root)
            utils.export_stl(design, final_save_dir, components, mesh_quality, original_base_link_name)   
            
            progress_dialog.progressValue = 100
            adsk.doEvents()
            progress_dialog.hide()
            
            completion_msg = (f'🎉 {msg}\n\n'
                            f'📁 Package saved to:\n{final_save_dir}\n\n'
                            f'↩️ IMPORTANT: Please undo the last change using Ctrl+Z or the back arrow\n'
                            f'🚧 in the timeline to revert the duplicated components created by the exporter.\n\n'
                            f'🚀 Your robot is ready for ROS!')
            
            ui.messageBox(completion_msg, title)
        except:
            if progress_dialog:
                progress_dialog.hide()
            if ui:
                ui.messageBox(f'❌ Failed:\n{traceback.format_exc()}', title)


class ExporterValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global save_dir_global, base_link_component
            if not save_dir_global or not os.path.exists(save_dir_global):
                args.areInputsValid = False
                return
            if not base_link_component or base_link_component in ["None", "+++ Select Base Component +++"]:
                args.areInputsValid = False
                return
            args.areInputsValid = True
        except:
            args.areInputsValid = False


class ExporterCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global save_dir_global, mesh_quality, base_link_component
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
            
            # Base Link Selection
            base_group = inputs.addGroupCommandInput('base_group', '⛓️ Base Link Selection')
            
            base_dropdown = base_group.children.addDropDownCommandInput(
                'base_link_dropdown', 
                '⚙️ Select Base Component:', 
                adsk.core.DropDownStyles.LabeledIconDropDownStyle
            )
            base_items = base_dropdown.listItems
            
            # Add a "None" option as the first item
            base_items.add('+++ Select Base Component +++', True, '')
            
            # Add all occurrences
            for occ in root.occurrences:
                clean_name_str = re.sub('[ :()]', '_', occ.name)
                base_items.add(clean_name_str, False, '')
            
            # Set default selection to "None"
            base_link_component = "+++ Select Base Component +++"
            
            inputs.addSeparatorCommandInput('sep0')
            
            # Export Location
            path_group = inputs.addGroupCommandInput('path_group', '📁 Export Location ⚠️ Select a valid directory')
            path_group.children.addTextBoxCommandInput('dir_text_box', '➡️ Export Path:', 'No folder selected...', 1, True)
            select_btn = path_group.children.addBoolValueInput('select_loc_btn', '📁 Select Export Folder', False, '', True)
            select_btn.text = '📦 Browse...'
            
            inputs.addSeparatorCommandInput('sep1')
            
            # Mesh Export Settings
            mesh_group = inputs.addGroupCommandInput('mesh_group', '📄 Mesh Export Settings')
            
            mesh_dropdown = mesh_group.children.addDropDownCommandInput(
                'mesh_quality_dropdown', 
                '⚙️ Mesh Quality:', 
                adsk.core.DropDownStyles.LabeledIconDropDownStyle
            )
            mesh_items = mesh_dropdown.listItems
            
            mesh_items.add('⭐ Low (Fastest, Smallest files)', False)
            mesh_items.add('⭐⭐ Medium (Balanced - Default)', True)
            mesh_items.add('⭐⭐⭐ High (Slower, Larger files)', False)
            
            mesh_quality = 'Medium'
            for i in range(mesh_items.count):
                if 'Medium' in mesh_items.item(i).name:
                    mesh_items.item(i).isSelected = True
                    break
            
            inputs.addSeparatorCommandInput('sep2')
            
            # Preview Joints Section
            preview_group = inputs.addGroupCommandInput('preview_group', '🔗 Preview Joints')
            
            # Statistics text box - clean, minimal
            preview_stats = preview_group.children.addTextBoxCommandInput(
                'preview_stats', 
                '📊 Statistics:', 
                '⏳ Select a base component to preview', 
                3,  # Height in lines
                True  # Read-only
            )
            
            # Separator between Statistics and Joint Tree
            inputs.addSeparatorCommandInput('sep_preview')
            
            # Tree view text box
            preview_tree = preview_group.children.addTextBoxCommandInput(
                'preview_tree', 
                '📋 Joint Tree:', 
                'Waiting for selection...', 
                14,  # Height in lines
                True  # Read-only
            )
            
            # Refresh button
            refresh_btn = preview_group.children.addBoolValueInput(
                'refresh_preview_btn', 
                '🔄 Refresh Preview', 
                False, 
                '', 
                True
            )
            refresh_btn.text = '🔄 Refresh'
            
            # Store references to UI elements for updating
            cmd.preview_stats = preview_stats
            cmd.preview_tree = preview_tree
            
            inputs.addSeparatorCommandInput('sep3')
            
            # Generate button
            cmd.okButtonText = '💾 Generate URDF Package'
            cmd.okButtonIsEnabled = False
            
            # Don't auto-preview on load - wait for user selection
            
        except:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox(f'❌ Failed to build dialog workspace:\n{traceback.format_exc()}')


class ExporterInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global save_dir_global, mesh_quality, base_link_component
            app = adsk.core.Application.get()
            ui = app.userInterface
            cmdInput = args.input
            inputs = cmdInput.commandInputs
            
            if cmdInput.id == 'base_link_dropdown':
                if cmdInput.selectedItem:
                    base_link_component = cmdInput.selectedItem.name
                    cmd = cmdInput.parentCommand
                    
                    # Update preview when base link changes (if valid selection)
                    try:
                        app = adsk.core.Application.get()
                        design = adsk.fusion.Design.cast(app.activeProduct)
                        if design:
                            root = design.rootComponent
                            
                            # Check if valid selection (not the placeholder)
                            if base_link_component and base_link_component not in ["None", "+++ Select Base Component +++"]:
                                stats_text, tree_text, _ = get_joint_preview(root, base_link_component)
                            else:
                                # Show waiting message
                                stats_text = "⏳ Select a base component to preview"
                                tree_text = "Waiting for selection..."
                            
                            # Update preview text boxes
                            preview_stats = inputs.itemById('preview_stats')
                            preview_tree = inputs.itemById('preview_tree')
                            if preview_stats:
                                preview_stats.text = stats_text
                            if preview_tree:
                                preview_tree.text = tree_text
                    except Exception as e:
                        # If preview fails, show error but don't crash
                        try:
                            preview_stats = inputs.itemById('preview_stats')
                            preview_tree = inputs.itemById('preview_tree')
                            if preview_stats:
                                preview_stats.text = f"❌ Preview error: {str(e)[:50]}"
                            if preview_tree:
                                preview_tree.text = "Please try refreshing or selecting another component"
                        except:
                            pass
                    
                    if cmd:
                        # Check if valid selection (not placeholder)
                        is_valid = (save_dir_global and os.path.exists(save_dir_global) 
                                   and base_link_component 
                                   and base_link_component not in ["None", "+++ Select Base Component +++"])
                        cmd.okButtonIsEnabled = is_valid
            
            elif cmdInput.id == 'refresh_preview_btn':
                # Refresh preview when button is clicked
                try:
                    app = adsk.core.Application.get()
                    design = adsk.fusion.Design.cast(app.activeProduct)
                    if design and base_link_component and base_link_component not in ["None", "+++ Select Base Component +++"]:
                        root = design.rootComponent
                        stats_text, tree_text, _ = get_joint_preview(root, base_link_component)
                        
                        preview_stats = inputs.itemById('preview_stats')
                        preview_tree = inputs.itemById('preview_tree')
                        if preview_stats:
                            preview_stats.text = stats_text
                        if preview_tree:
                            preview_tree.text = tree_text
                    else:
                        # Show waiting message
                        preview_stats = inputs.itemById('preview_stats')
                        preview_tree = inputs.itemById('preview_tree')
                        if preview_stats:
                            preview_stats.text = "⏳ Select a base component to preview"
                        if preview_tree:
                            preview_tree.text = "Waiting for selection..."
                except Exception as e:
                    # If preview fails, show error but don't crash
                    try:
                        preview_stats = inputs.itemById('preview_stats')
                        preview_tree = inputs.itemById('preview_tree')
                        if preview_stats:
                            preview_stats.text = f"❌ Preview error: {str(e)[:50]}"
                        if preview_tree:
                            preview_tree.text = "Please try refreshing or selecting another component"
                    except:
                        pass
            
            elif cmdInput.id == 'select_loc_btn':
                folder_chosen = utils.file_dialog(ui)
                if folder_chosen:
                    save_dir_global = folder_chosen
                    path_display = inputs.itemById('dir_text_box')
                    if path_display:
                        path_display.text = save_dir_global
                    
                    cmd = cmdInput.parentCommand
                    if cmd:
                        # Check if valid selection (not placeholder)
                        is_valid = (save_dir_global and os.path.exists(save_dir_global) 
                                   and base_link_component 
                                   and base_link_component not in ["None", "+++ Select Base Component +++"])
                        cmd.okButtonIsEnabled = is_valid
            
            elif cmdInput.id == 'mesh_quality_dropdown':
                if cmdInput.selectedItem:
                    selected_text = cmdInput.selectedItem.name
                    if 'Low' in selected_text:
                        mesh_quality = 'Low'
                    elif 'Medium' in selected_text:
                        mesh_quality = 'Medium'
                    elif 'High' in selected_text:
                        mesh_quality = 'High'
                    else:
                        mesh_quality = 'Medium'
                    print(f'⚙️ Mesh quality set to: {mesh_quality}')
                    
        except:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox(f'❌ Input change handler failure:\n{traceback.format_exc()}')


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        global save_dir_global, mesh_quality, base_link_component
        save_dir_global = ""
        mesh_quality = "Medium"
        base_link_component = ""

        cmd_def = ui.commandDefinitions.itemById('URDF_Exporter_GUI_Cmd')
        if cmd_def:
            cmd_def.deleteMe()
            
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            'URDF_Exporter_GUI_Cmd', 
            '🤖 Export URDF Package', 
            '🚀 Generate a complete ROS URDF package from your Fusion 360 design.\n⚙️ Includes URDF, meshes, launch files, and controllers.'
        )
        
        onCreated = ExporterCommandCreatedHandler()
        cmd_def.commandCreated.add(onCreated)
        handlers.append(onCreated)
        
        cmd_def.execute()
        adsk.autoTerminate(False)
        
    except:
        if ui:
            ui.messageBox(f'❌ Initialization Engine Failed:\n{traceback.format_exc()}')