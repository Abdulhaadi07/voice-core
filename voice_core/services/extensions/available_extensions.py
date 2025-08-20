import logging
from typing import List, Dict
from voice_core.tenant.models import Tenant
from voice_core.users.models import ExtensionAssignment

logger = logging.getLogger(__name__)


def get_available_extensions(tenant_id: int) -> Dict[str, List[int]]:
    """
    Get available extensions for a specific tenant, grouped by context.
    
    Args:
        tenant_id: The primary key of the tenant
        
    Returns:
        Dictionary with context names as keys and lists of available extensions as values
    """
    try:
        # Get tenant from tenant.pk = tenant_id
        tenant = Tenant.objects.get(pk=tenant_id)
        logger.info(f"Getting available extensions for tenant: {tenant.name} (ID: {tenant_id})")
        
        # Get all contexts from tenant.contexts (supports list or legacy dict)
        raw_contexts = tenant.contexts or []
        if isinstance(raw_contexts, dict):
            contexts_list = list(raw_contexts.values())
        else:
            contexts_list = raw_contexts
        logger.debug(f"Tenant contexts: {contexts_list}")
        
        # Get all assigned extensions from ExtensionAssignment
        assigned_extensions = ExtensionAssignment.objects.filter(
            user__tenant=tenant
        ).values_list('extension', flat=True)
        
        assigned_extensions = [int(ext) for ext in assigned_extensions]
        logger.debug(f"Assigned extensions for tenant: {assigned_extensions}")
        
        # Dictionary to store available extensions per context
        context_available_extensions = {}
        
        for context_data in contexts_list:
            if 'user_ranges' in context_data:
                context_name = context_data.get('name')
                context_label = context_data.get('label')
                context_uuid = context_data.get('uuid', '')
                # derive fallback names if missing
                if not context_name and context_uuid:
                    context_name = f"Context-{context_uuid}"
                if not context_label and context_uuid:
                    context_label = f"Context-{context_uuid}"
                
                # Use label as the key, fallback to name if label is empty
                context_key = context_name
                
                # Generate all possible extensions for this context
                context_possible_extensions = []
                for user_range in context_data['user_ranges']:
                    start = int(user_range.get('start', 0))
                    end = int(user_range.get('end', 0))
                    
                    # Generate range of extensions
                    context_extensions = list(range(start, end + 1))
                    context_possible_extensions.extend(context_extensions)
                    logger.debug(f"Context {context_key}: extensions {start}-{end} = {context_extensions}")
                
                # Remove duplicates and sort
                context_possible_extensions = sorted(list(set(context_possible_extensions)))
                
                # Remove assigned extensions to get available ones for this context
                context_available = [ext for ext in context_possible_extensions if ext not in assigned_extensions]
                
                # Add context even if it has no available extensions (for completeness)
                context_available_extensions[context_key] = context_available
                logger.debug(f"Context {context_key}: {len(context_available)} available extensions out of {len(context_possible_extensions)} total")
        
        logger.info(f"Found available extensions for {len(context_available_extensions)} contexts in tenant {tenant.name}")
        return context_available_extensions
        
    except Tenant.DoesNotExist:
        logger.error(f"Tenant with ID {tenant_id} does not exist")
        return {}
    except Exception as e:
        logger.error(f"Error getting available extensions for tenant {tenant_id}: {str(e)}", exc_info=True)
        return {}

