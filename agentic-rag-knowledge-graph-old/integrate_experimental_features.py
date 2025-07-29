"""
Safe integration script using AST parsing instead of string replacement.
This ensures code modifications are done properly without breaking syntax.
"""

import ast
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Union

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SafeCodeModifier(ast.NodeTransformer):
    """Base class for safe AST-based code modifications."""
    
    def __init__(self):
        self.modified = False
        self.errors = []
    
    def safe_parse(self, code: str) -> Optional[ast.Module]:
        """Safely parse Python code into AST."""
        try:
            return ast.parse(code)
        except SyntaxError as e:
            self.errors.append(f"Syntax error in original code: {e}")
            return None
    
    def safe_unparse(self, tree: ast.Module) -> Optional[str]:
        """Safely convert AST back to Python code."""
        try:
            # Python 3.9+ has ast.unparse
            if hasattr(ast, 'unparse'):
                return ast.unparse(tree)
            else:
                # Fallback for older Python versions
                import astor
                return astor.to_source(tree)
        except Exception as e:
            self.errors.append(f"Failed to generate code: {e}")
            return None


class ToolsCacheIntegrator(SafeCodeModifier):
    """Integrate caching into tools.py using AST."""
    
    def __init__(self):
        super().__init__()
        self.cache_imports_added = False
        self.hybrid_search_decorated = False
        self.embedding_cache_added = False
    
    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Add imports at module level."""
        # Find the position after existing imports
        import_insert_pos = 0
        for i, item in enumerate(node.body):
            if isinstance(item, (ast.Import, ast.ImportFrom)):
                import_insert_pos = i + 1
            else:
                break
        
        # Add cache imports if not present
        cache_imports = [
            ast.ImportFrom(
                module='.cache_manager',
                names=[
                    ast.alias(name='cached_search', asname=None),
                    ast.alias(name='get_embedding_cache', asname=None)
                ],
                level=0
            ),
            ast.ImportFrom(
                module='.error_handler',
                names=[
                    ast.alias(name='retry_with_backoff', asname=None),
                    ast.alias(name='get_circuit_breaker', asname=None),
                    ast.alias(name='handle_error', asname=None)
                ],
                level=0
            )
        ]
        
        # Check if imports already exist
        existing_modules = set()
        for item in node.body[:import_insert_pos]:
            if isinstance(item, ast.ImportFrom) and item.module:
                existing_modules.add(item.module)
        
        # Add only missing imports
        new_imports = []
        for imp in cache_imports:
            if imp.module not in existing_modules:
                new_imports.append(imp)
                self.cache_imports_added = True
        
        if new_imports:
            node.body[import_insert_pos:import_insert_pos] = new_imports
            self.modified = True
        
        # Continue visiting child nodes
        self.generic_visit(node)
        return node
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        """Add decorators and modify function bodies."""
        if node.name == 'hybrid_search_tool':
            # Add decorators if not present
            decorator_names = [d.id if isinstance(d, ast.Name) else 
                             d.func.id if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) else None 
                             for d in node.decorator_list]
            
            if 'cached_search' not in decorator_names:
                # Add @cached_search() decorator
                node.decorator_list.insert(0, ast.Call(
                    func=ast.Name(id='cached_search', ctx=ast.Load()),
                    args=[],
                    keywords=[]
                ))
                self.hybrid_search_decorated = True
                self.modified = True
            
            if 'retry_with_backoff' not in decorator_names:
                # Add @retry_with_backoff decorator
                node.decorator_list.insert(1, ast.Call(
                    func=ast.Name(id='retry_with_backoff', ctx=ast.Load()),
                    args=[],
                    keywords=[ast.keyword(arg='max_retries', value=ast.Constant(value=3))]
                ))
                self.modified = True
            
            # Modify function body to add embedding cache
            self._add_embedding_cache_to_function(node)
        
        self.generic_visit(node)
        return node
    
    def _add_embedding_cache_to_function(self, node: ast.AsyncFunctionDef):
        """Add embedding cache logic to hybrid_search_tool function."""
        # Find where embedding is generated
        for i, stmt in enumerate(node.body):
            if self._is_embedding_generation(stmt):
                # Create cache check code
                cache_check = self._create_embedding_cache_code()
                # Replace the original embedding generation
                node.body[i:i+1] = cache_check
                self.embedding_cache_added = True
                self.modified = True
                break
    
    def _is_embedding_generation(self, stmt) -> bool:
        """Check if statement is embedding generation."""
        if isinstance(stmt, ast.Assign):
            # Check for: embedding = await embedder.generate_embedding(query)
            if (len(stmt.targets) == 1 and 
                isinstance(stmt.targets[0], ast.Name) and 
                stmt.targets[0].id == 'embedding' and
                isinstance(stmt.value, ast.Await)):
                return True
        return False
    
    def _create_embedding_cache_code(self) -> List[ast.stmt]:
        """Create AST nodes for embedding cache logic."""
        # This creates the equivalent of:
        # embedding_cache = get_embedding_cache()
        # cached_embedding = embedding_cache.get(query)
        # if cached_embedding:
        #     embedding = cached_embedding
        #     logger.info("Using cached embedding")
        # else:
        #     embedder_breaker = get_circuit_breaker("embedder", failure_threshold=3)
        #     try:
        #         embedding = await embedder_breaker.async_call(embedder.generate_embedding, query)
        #         embedding_cache.set(query, embedding)
        #     except Exception as e:
        #         logger.error(f"Embedding generation failed: {e}")
        #         handle_error(e, {"query": query})
        #         return []
        
        return [
            # embedding_cache = get_embedding_cache()
            ast.Assign(
                targets=[ast.Name(id='embedding_cache', ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='get_embedding_cache', ctx=ast.Load()), args=[], keywords=[])
            ),
            # cached_embedding = embedding_cache.get(query)
            ast.Assign(
                targets=[ast.Name(id='cached_embedding', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='embedding_cache', ctx=ast.Load()),
                        attr='get',
                        ctx=ast.Load()
                    ),
                    args=[ast.Name(id='query', ctx=ast.Load())],
                    keywords=[]
                )
            ),
            # if cached_embedding: ... else: ...
            ast.If(
                test=ast.Name(id='cached_embedding', ctx=ast.Load()),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id='embedding', ctx=ast.Store())],
                        value=ast.Name(id='cached_embedding', ctx=ast.Load())
                    ),
                    ast.Expr(value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id='logger', ctx=ast.Load()),
                            attr='info',
                            ctx=ast.Load()
                        ),
                        args=[ast.Constant(value="Using cached embedding")],
                        keywords=[]
                    ))
                ],
                orelse=self._create_embedding_generation_with_breaker()
            )
        ]
    
    def _create_embedding_generation_with_breaker(self) -> List[ast.stmt]:
        """Create embedding generation with circuit breaker."""
        return [
            # embedder_breaker = get_circuit_breaker("embedder", failure_threshold=3)
            ast.Assign(
                targets=[ast.Name(id='embedder_breaker', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id='get_circuit_breaker', ctx=ast.Load()),
                    args=[ast.Constant(value="embedder")],
                    keywords=[ast.keyword(arg='failure_threshold', value=ast.Constant(value=3))]
                )
            ),
            # try: ... except Exception as e: ...
            ast.Try(
                body=[
                    # embedding = await embedder_breaker.async_call(...)
                    ast.Assign(
                        targets=[ast.Name(id='embedding', ctx=ast.Store())],
                        value=ast.Await(value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id='embedder_breaker', ctx=ast.Load()),
                                attr='async_call',
                                ctx=ast.Load()
                            ),
                            args=[
                                ast.Attribute(
                                    value=ast.Name(id='embedder', ctx=ast.Load()),
                                    attr='generate_embedding',
                                    ctx=ast.Load()
                                ),
                                ast.Name(id='query', ctx=ast.Load())
                            ],
                            keywords=[]
                        ))
                    ),
                    # embedding_cache.set(query, embedding)
                    ast.Expr(value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id='embedding_cache', ctx=ast.Load()),
                            attr='set',
                            ctx=ast.Load()
                        ),
                        args=[
                            ast.Name(id='query', ctx=ast.Load()),
                            ast.Name(id='embedding', ctx=ast.Load())
                        ],
                        keywords=[]
                    ))
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id='Exception', ctx=ast.Load()),
                        name='e',
                        body=[
                            # logger.error(...)
                            ast.Expr(value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id='logger', ctx=ast.Load()),
                                    attr='error',
                                    ctx=ast.Load()
                                ),
                                args=[ast.JoinedStr(values=[
                                    ast.Constant(value="Embedding generation failed: "),
                                    ast.FormattedValue(value=ast.Name(id='e', ctx=ast.Load()), conversion=-1)
                                ])],
                                keywords=[]
                            )),
                            # handle_error(e, {"query": query})
                            ast.Expr(value=ast.Call(
                                func=ast.Name(id='handle_error', ctx=ast.Load()),
                                args=[
                                    ast.Name(id='e', ctx=ast.Load()),
                                    ast.Dict(
                                        keys=[ast.Constant(value='query')],
                                        values=[ast.Name(id='query', ctx=ast.Load())]
                                    )
                                ],
                                keywords=[]
                            )),
                            # return []
                            ast.Return(value=ast.List(elts=[], ctx=ast.Load()))
                        ]
                    )
                ],
                orelse=[],
                finalbody=[]
            )
        ]
    
    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Update function calls to use optimized versions."""
        # Replace hybrid_search_unified with hybrid_search_optimized
        if (isinstance(node.func, ast.Name) and node.func.id == 'hybrid_search_unified'):
            node.func.id = 'hybrid_search_optimized'
            self.modified = True
        
        self.generic_visit(node)
        return node


class APICacheEndpointsIntegrator(SafeCodeModifier):
    """Add cache endpoints to api.py using AST."""
    
    def __init__(self):
        super().__init__()
        self.imports_added = False
        self.endpoints_added = False
    
    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Add imports and endpoints at module level."""
        # Add imports
        self._add_cache_imports(node)
        
        # Add endpoints after existing endpoints
        self._add_cache_endpoints(node)
        
        self.generic_visit(node)
        return node
    
    def _add_cache_imports(self, node: ast.Module):
        """Add cache-related imports."""
        # Find import position
        import_insert_pos = 0
        for i, item in enumerate(node.body):
            if isinstance(item, (ast.Import, ast.ImportFrom)):
                import_insert_pos = i + 1
            else:
                break
        
        # Check if imports exist
        existing_imports = set()
        for item in node.body[:import_insert_pos]:
            if isinstance(item, ast.ImportFrom) and item.module:
                existing_imports.add(item.module)
        
        # Add missing imports
        if '.cache_manager' not in existing_imports:
            cache_import = ast.ImportFrom(
                module='.cache_manager',
                names=[
                    ast.alias(name='get_cache_stats', asname=None),
                    ast.alias(name='clear_cache', asname=None),
                    ast.alias(name='warm_cache_with_common_queries', asname=None)
                ],
                level=0
            )
            node.body.insert(import_insert_pos, cache_import)
            self.imports_added = True
            self.modified = True
        
        if '.error_handler' not in existing_imports:
            error_import = ast.ImportFrom(
                module='.error_handler',
                names=[ast.alias(name='check_system_health', asname=None)],
                level=0
            )
            node.body.insert(import_insert_pos, error_import)
            self.modified = True
    
    def _add_cache_endpoints(self, node: ast.Module):
        """Add cache API endpoints."""
        # Find a good position to add endpoints (after existing endpoints)
        insert_pos = len(node.body)
        
        # Look for existing endpoints to determine style
        for i in range(len(node.body) - 1, -1, -1):
            if isinstance(node.body[i], ast.AsyncFunctionDef):
                # Check if it's an endpoint by looking for decorators
                for dec in node.body[i].decorator_list:
                    if self._is_endpoint_decorator(dec):
                        insert_pos = i + 1
                        break
        
        # Check if endpoints already exist
        existing_endpoints = set()
        for item in node.body:
            if isinstance(item, ast.AsyncFunctionDef):
                existing_endpoints.add(item.name)
        
        # Create and add new endpoints
        new_endpoints = []
        
        if 'cache_stats' not in existing_endpoints:
            new_endpoints.append(self._create_cache_stats_endpoint())
        
        if 'cache_clear' not in existing_endpoints:
            new_endpoints.append(self._create_cache_clear_endpoint())
        
        if 'cache_warm' not in existing_endpoints:
            new_endpoints.append(self._create_cache_warm_endpoint())
        
        if 'system_health_detailed' not in existing_endpoints:
            new_endpoints.append(self._create_health_detailed_endpoint())
        
        if new_endpoints:
            node.body[insert_pos:insert_pos] = new_endpoints
            self.endpoints_added = True
            self.modified = True
    
    def _is_endpoint_decorator(self, dec) -> bool:
        """Check if decorator is an endpoint decorator like @app.get()."""
        if isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Attribute):
                if (isinstance(dec.func.value, ast.Name) and 
                    dec.func.value.id == 'app' and
                    dec.func.attr in ['get', 'post', 'put', 'delete']):
                    return True
        return False
    
    def _create_cache_stats_endpoint(self) -> ast.AsyncFunctionDef:
        """Create cache stats endpoint AST."""
        return ast.AsyncFunctionDef(
            name='cache_stats',
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=[
                ast.Expr(value=ast.Constant(value='Get cache statistics.')),
                ast.Try(
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id='stats', ctx=ast.Store())],
                            value=ast.Await(value=ast.Call(
                                func=ast.Name(id='get_cache_stats', ctx=ast.Load()),
                                args=[],
                                keywords=[]
                            ))
                        ),
                        ast.Return(value=ast.Call(
                            func=ast.Name(id='JSONResponse', ctx=ast.Load()),
                            args=[],
                            keywords=[ast.keyword(arg='content', value=ast.Name(id='stats', ctx=ast.Load()))]
                        ))
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='Exception', ctx=ast.Load()),
                            name='e',
                            body=[
                                ast.Expr(value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id='logger', ctx=ast.Load()),
                                        attr='error',
                                        ctx=ast.Load()
                                    ),
                                    args=[ast.JoinedStr(values=[
                                        ast.Constant(value="Failed to get cache stats: "),
                                        ast.FormattedValue(value=ast.Name(id='e', ctx=ast.Load()), conversion=-1)
                                    ])],
                                    keywords=[]
                                )),
                                ast.Raise(exc=ast.Call(
                                    func=ast.Name(id='HTTPException', ctx=ast.Load()),
                                    args=[],
                                    keywords=[
                                        ast.keyword(arg='status_code', value=ast.Constant(value=500)),
                                        ast.keyword(arg='detail', value=ast.Call(
                                            func=ast.Name(id='str', ctx=ast.Load()),
                                            args=[ast.Name(id='e', ctx=ast.Load())],
                                            keywords=[]
                                        ))
                                    ]
                                ))
                            ]
                        )
                    ],
                    orelse=[],
                    finalbody=[]
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='app', ctx=ast.Load()),
                        attr='get',
                        ctx=ast.Load()
                    ),
                    args=[ast.Constant(value='/cache/stats')],
                    keywords=[]
                )
            ],
            returns=None,
            type_comment=None
        )
    
    def _create_cache_clear_endpoint(self) -> ast.AsyncFunctionDef:
        """Create cache clear endpoint AST."""
        # Similar structure to cache_stats but with POST and different logic
        return ast.AsyncFunctionDef(
            name='cache_clear',
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=[
                ast.Expr(value=ast.Constant(value='Clear the cache.')),
                ast.Try(
                    body=[
                        ast.Expr(value=ast.Await(value=ast.Call(
                            func=ast.Name(id='clear_cache', ctx=ast.Load()),
                            args=[],
                            keywords=[]
                        ))),
                        ast.Return(value=ast.Dict(
                            keys=[ast.Constant(value='message')],
                            values=[ast.Constant(value='Cache cleared successfully')]
                        ))
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='Exception', ctx=ast.Load()),
                            name='e',
                            body=[
                                ast.Expr(value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id='logger', ctx=ast.Load()),
                                        attr='error',
                                        ctx=ast.Load()
                                    ),
                                    args=[ast.JoinedStr(values=[
                                        ast.Constant(value="Failed to clear cache: "),
                                        ast.FormattedValue(value=ast.Name(id='e', ctx=ast.Load()), conversion=-1)
                                    ])],
                                    keywords=[]
                                )),
                                ast.Raise(exc=ast.Call(
                                    func=ast.Name(id='HTTPException', ctx=ast.Load()),
                                    args=[],
                                    keywords=[
                                        ast.keyword(arg='status_code', value=ast.Constant(value=500)),
                                        ast.keyword(arg='detail', value=ast.Call(
                                            func=ast.Name(id='str', ctx=ast.Load()),
                                            args=[ast.Name(id='e', ctx=ast.Load())],
                                            keywords=[]
                                        ))
                                    ]
                                ))
                            ]
                        )
                    ],
                    orelse=[],
                    finalbody=[]
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='app', ctx=ast.Load()),
                        attr='post',
                        ctx=ast.Load()
                    ),
                    args=[ast.Constant(value='/cache/clear')],
                    keywords=[]
                )
            ],
            returns=None,
            type_comment=None
        )
    
    def _create_cache_warm_endpoint(self) -> ast.AsyncFunctionDef:
        """Create cache warming endpoint AST."""
        return ast.AsyncFunctionDef(
            name='cache_warm',
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=[
                ast.Expr(value=ast.Constant(value='Warm the cache with common queries.')),
                ast.Try(
                    body=[
                        ast.Expr(value=ast.Await(value=ast.Call(
                            func=ast.Name(id='warm_cache_with_common_queries', ctx=ast.Load()),
                            args=[],
                            keywords=[]
                        ))),
                        ast.Return(value=ast.Dict(
                            keys=[ast.Constant(value='message')],
                            values=[ast.Constant(value='Cache warmed successfully')]
                        ))
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='Exception', ctx=ast.Load()),
                            name='e',
                            body=[
                                ast.Expr(value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id='logger', ctx=ast.Load()),
                                        attr='error',
                                        ctx=ast.Load()
                                    ),
                                    args=[ast.JoinedStr(values=[
                                        ast.Constant(value="Failed to warm cache: "),
                                        ast.FormattedValue(value=ast.Name(id='e', ctx=ast.Load()), conversion=-1)
                                    ])],
                                    keywords=[]
                                )),
                                ast.Raise(exc=ast.Call(
                                    func=ast.Name(id='HTTPException', ctx=ast.Load()),
                                    args=[],
                                    keywords=[
                                        ast.keyword(arg='status_code', value=ast.Constant(value=500)),
                                        ast.keyword(arg='detail', value=ast.Call(
                                            func=ast.Name(id='str', ctx=ast.Load()),
                                            args=[ast.Name(id='e', ctx=ast.Load())],
                                            keywords=[]
                                        ))
                                    ]
                                ))
                            ]
                        )
                    ],
                    orelse=[],
                    finalbody=[]
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='app', ctx=ast.Load()),
                        attr='post',
                        ctx=ast.Load()
                    ),
                    args=[ast.Constant(value='/cache/warm')],
                    keywords=[]
                )
            ],
            returns=None,
            type_comment=None
        )
    
    def _create_health_detailed_endpoint(self) -> ast.AsyncFunctionDef:
        """Create detailed health check endpoint AST."""
        return ast.AsyncFunctionDef(
            name='system_health_detailed',
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=[
                ast.Expr(value=ast.Constant(value='Get detailed system health including circuit breakers.')),
                ast.Try(
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id='health', ctx=ast.Store())],
                            value=ast.Await(value=ast.Call(
                                func=ast.Name(id='check_system_health', ctx=ast.Load()),
                                args=[],
                                keywords=[
                                    ast.keyword(arg='db_pool', value=ast.Attribute(
                                        value=ast.Attribute(
                                            value=ast.Name(id='app', ctx=ast.Load()),
                                            attr='state',
                                            ctx=ast.Load()
                                        ),
                                        attr='db_pool',
                                        ctx=ast.Load()
                                    )),
                                    ast.keyword(arg='graph_driver', value=ast.Attribute(
                                        value=ast.Attribute(
                                            value=ast.Name(id='app', ctx=ast.Load()),
                                            attr='state',
                                            ctx=ast.Load()
                                        ),
                                        attr='graph_driver',
                                        ctx=ast.Load()
                                    ))
                                ]
                            ))
                        ),
                        ast.Return(value=ast.Call(
                            func=ast.Name(id='JSONResponse', ctx=ast.Load()),
                            args=[],
                            keywords=[ast.keyword(arg='content', value=ast.Name(id='health', ctx=ast.Load()))]
                        ))
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id='Exception', ctx=ast.Load()),
                            name='e',
                            body=[
                                ast.Expr(value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id='logger', ctx=ast.Load()),
                                        attr='error',
                                        ctx=ast.Load()
                                    ),
                                    args=[ast.JoinedStr(values=[
                                        ast.Constant(value="Health check failed: "),
                                        ast.FormattedValue(value=ast.Name(id='e', ctx=ast.Load()), conversion=-1)
                                    ])],
                                    keywords=[]
                                )),
                                ast.Raise(exc=ast.Call(
                                    func=ast.Name(id='HTTPException', ctx=ast.Load()),
                                    args=[],
                                    keywords=[
                                        ast.keyword(arg='status_code', value=ast.Constant(value=500)),
                                        ast.keyword(arg='detail', value=ast.Call(
                                            func=ast.Name(id='str', ctx=ast.Load()),
                                            args=[ast.Name(id='e', ctx=ast.Load())],
                                            keywords=[]
                                        ))
                                    ]
                                ))
                            ]
                        )
                    ],
                    orelse=[],
                    finalbody=[]
                )
            ],
            decorator_list=[
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='app', ctx=ast.Load()),
                        attr='get',
                        ctx=ast.Load()
                    ),
                    args=[ast.Constant(value='/system/health/detailed')],
                    keywords=[]
                )
            ],
            returns=None,
            type_comment=None
        )


async def integrate_tools_safely():
    """Safely integrate caching into tools.py using AST."""
    tools_path = Path("agent/tools.py")
    
    if not tools_path.exists():
        logger.error(f"tools.py not found at {tools_path}")
        return False
    
    # Read the original code
    original_code = tools_path.read_text()
    
    # Create integrator and process
    integrator = ToolsCacheIntegrator()
    tree = integrator.safe_parse(original_code)
    
    if not tree:
        logger.error(f"Failed to parse tools.py: {integrator.errors}")
        return False
    
    # Apply transformations
    modified_tree = integrator.visit(tree)
    
    if not integrator.modified:
        logger.info("tools.py already has all modifications")
        return True
    
    # Generate new code
    new_code = integrator.safe_unparse(modified_tree)
    
    if not new_code:
        logger.error(f"Failed to generate code: {integrator.errors}")
        return False
    
    # Backup original file
    backup_path = tools_path.with_suffix('.py.backup')
    backup_path.write_text(original_code)
    logger.info(f"Created backup at {backup_path}")
    
    # Write modified code
    tools_path.write_text(new_code)
    logger.info(f"Successfully updated tools.py")
    logger.info(f"  - Cache imports added: {integrator.cache_imports_added}")
    logger.info(f"  - Hybrid search decorated: {integrator.hybrid_search_decorated}")
    logger.info(f"  - Embedding cache added: {integrator.embedding_cache_added}")
    
    return True


async def integrate_api_safely():
    """Safely integrate cache endpoints into api.py using AST."""
    api_path = Path("agent/api.py")
    
    if not api_path.exists():
        logger.error(f"api.py not found at {api_path}")
        return False
    
    # Read the original code
    original_code = api_path.read_text()
    
    # Create integrator and process
    integrator = APICacheEndpointsIntegrator()
    tree = integrator.safe_parse(original_code)
    
    if not tree:
        logger.error(f"Failed to parse api.py: {integrator.errors}")
        return False
    
    # Apply transformations
    modified_tree = integrator.visit(tree)
    
    if not integrator.modified:
        logger.info("api.py already has all modifications")
        return True
    
    # Generate new code
    new_code = integrator.safe_unparse(modified_tree)
    
    if not new_code:
        logger.error(f"Failed to generate code: {integrator.errors}")
        return False
    
    # Backup original file
    backup_path = api_path.with_suffix('.py.backup')
    backup_path.write_text(original_code)
    logger.info(f"Created backup at {backup_path}")
    
    # Write modified code
    api_path.write_text(new_code)
    logger.info(f"Successfully updated api.py")
    logger.info(f"  - Imports added: {integrator.imports_added}")
    logger.info(f"  - Endpoints added: {integrator.endpoints_added}")
    
    return True


async def update_ingestion_to_use_optimized():
    """Update ingestion to use optimized embedder with safe replacement."""
    ingest_path = Path("ingestion/ingest.py")
    
    if not ingest_path.exists():
        logger.error(f"ingest.py not found at {ingest_path}")
        return False
    
    original_code = ingest_path.read_text()
    
    try:
        tree = ast.parse(original_code)
    except SyntaxError as e:
        logger.error(f"Failed to parse ingest.py: {e}")
        return False
    
    modified = False
    
    # Find and update import statements
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == '.embedder_jina' or node.module == 'embedder_jina':
                # Update the import
                for alias in node.names:
                    if alias.name == 'create_embedder':
                        node.module = '.embedder_jina_optimized'
                        alias.name = 'create_optimized_embedder'
                        alias.asname = 'create_embedder'
                        modified = True
                        break
    
    if not modified:
        logger.info("ingest.py already uses optimized embedder or import not found")
        return True
    
    # Generate new code
    try:
        if hasattr(ast, 'unparse'):
            new_code = ast.unparse(tree)
        else:
            import astor
            new_code = astor.to_source(tree)
    except Exception as e:
        logger.error(f"Failed to generate code: {e}")
        return False
    
    # Backup and write
    backup_path = ingest_path.with_suffix('.py.backup')
    backup_path.write_text(original_code)
    logger.info(f"Created backup at {backup_path}")
    
    ingest_path.write_text(new_code)
    logger.info("Updated ingest.py to use optimized embedder")
    
    return True


async def apply_sql_migrations():
    """Apply SQL migrations for optimized functions."""
    logger.info("Applying SQL migrations...")
    
    # Connect to database and apply migrations
    import asyncpg
    from dotenv import load_dotenv
    
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not found")
        return False
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Read and apply optimized hybrid search
        migration_path = Path("migrations/experimental_hybrid_search_v2.sql")
        if migration_path.exists():
            sql_content = migration_path.read_text()
            
            # Execute in a transaction
            async with conn.transaction():
                await conn.execute(sql_content)
            
            logger.info("Applied optimized hybrid search migration")
        else:
            logger.warning(f"Migration file not found: {migration_path}")
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply SQL migrations: {e}")
        return False


async def create_backups():
    """Create backups of all files that will be modified."""
    files_to_backup = [
        "agent/tools.py",
        "agent/api.py",
        "ingestion/ingest.py"
    ]
    
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for file_path in files_to_backup:
        path = Path(file_path)
        if path.exists():
            backup_path = backup_dir / f"{path.name}.{timestamp}.backup"
            backup_path.write_text(path.read_text())
            logger.info(f"Created backup: {backup_path}")
    
    logger.info(f"All backups created in {backup_dir}")


async def verify_syntax():
    """Verify that all modified files have valid Python syntax."""
    files_to_check = [
        "agent/tools.py",
        "agent/api.py",
        "ingestion/ingest.py"
    ]
    
    all_valid = True
    
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            try:
                code = path.read_text()
                ast.parse(code)
                logger.info(f"✓ {file_path} has valid syntax")
            except SyntaxError as e:
                logger.error(f"✗ {file_path} has syntax error: {e}")
                all_valid = False
        else:
            logger.warning(f"? {file_path} not found")
    
    return all_valid


async def main():
    """Apply all optimizations safely using AST parsing."""
    logger.info("Starting safe optimization integration using AST...")
    
    # Create backups first
    await create_backups()
    
    # Apply modifications
    success = True
    
    if not await integrate_tools_safely():
        logger.error("Failed to integrate tools.py")
        success = False
    
    if not await integrate_api_safely():
        logger.error("Failed to integrate api.py")
        success = False
    
    if not await update_ingestion_to_use_optimized():
        logger.error("Failed to update ingest.py")
        success = False
    
    # Verify syntax of all modified files
    if success:
        if not await verify_syntax():
            logger.error("Syntax verification failed!")
            success = False
    
    # Apply SQL migrations if all Python modifications succeeded
    if success:
        if not await apply_sql_migrations():
            logger.warning("SQL migrations failed but Python changes succeeded")
    
    if success:
        logger.info("✨ Safe optimization integration complete!")
        logger.info("\nNext steps:")
        logger.info("1. Review the backup files if needed")
        logger.info("2. Test the modified files to ensure they work correctly")
        logger.info("3. Restart the API server to load changes")
        logger.info("4. Test the new endpoints: /cache/stats, /cache/warm")
        logger.info("5. Monitor performance improvements")
    else:
        logger.error("⚠️  Integration had errors. Check logs and backup files.")
        logger.info("\nTo restore from backups:")
        logger.info("  cp backups/*.backup <original_location>")


if __name__ == "__main__":
    # Check Python version for AST.unparse availability
    import sys
    if sys.version_info < (3, 9) and not any(module in sys.modules for module in ['astor', 'astunparse']):
        logger.warning("Python < 3.9 detected. Installing astor for AST unparsing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "astor"])
    
    asyncio.run(main())
