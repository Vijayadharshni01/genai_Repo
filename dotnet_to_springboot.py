import zipfile
import os
import google.generativeai as genai

import json
import uuid

def unzip_and_convert_stream(zip_path, extract_to, output_folder):
    """Unzip .NET project and convert to Spring Boot, yielding results incrementally"""
    # Configure Gemini API
    genai.configure(api_key="")
    
    # Extract zip file
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    
    # Create output folder
    os.makedirs(output_folder, exist_ok=True)
    
    # Phase 1: Context Gathering
    print("Phase 1: Gathering Context...")
    context = {
        'AppDbContext': '',
        'Program': '',
        'Startup': '',
        'Csproj': ''
    }
    
    files_to_process = []
    
    for root, dirs, files in os.walk(extract_to):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, extract_to)
            
            # Read file content for context if needed
            if file == 'AppDbContext.cs' or (file.endswith('.cs') and 'DbContext' in file):
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    context['AppDbContext'] += f.read() + "\n"
            elif file == 'Program.cs':
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    context['Program'] = f.read()
            elif file == 'Startup.cs':
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    context['Startup'] = f.read()
            elif file.endswith('.csproj'):
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    context['Csproj'] = f.read()
            
            # Collect files for processing
            if file.endswith('.cs') or file == 'appsettings.json' or file.endswith('.csproj'):
                files_to_process.append((file_path, relative_path, file))

    # Phase 2: Processing and Conversion
    print("Phase 2: Converting Files...")
    if not files_to_process:
        yield {'type': 'error', 'message': "No suitable files found in the zip file!"}
        return

    processed_program = False  # To ensure we only generate main config once per Program.cs

    for file_path, relative_path, file in files_to_process:
        try:
            ignore_file = False
            java_filename = ""
            prompt = ""
            folder_name = ""
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                dotnet_code = f.read()

            # --- Logic for File Mapping & Prompts ---

            # 1. Repositories
            if 'Repositories' in relative_path:
                if file.startswith('I') and file.endswith('Repository.cs'):
                    # Interface -> Repository Interface (extends JpaRepository)
                    base_name = file[1:-3] # Remove 'I' and '.cs' -> "CartRepository"
                    java_filename = f"{base_name}.java" 
                    folder_name = "Repository"
                    prompt = f"""You are an expert Java Spring Boot developer specializing in Spring Data JPA repository design.

                Convert the following .NET Entity Framework Core repository interface(s) into equivalent Java Spring Boot repository interface(s).

                ═══════════════════════════════════════════════════════════════════════════════
                CRITICAL RULES - FOLLOW EXACTLY:
                ═══════════════════════════════════════════════════════════════════════════════

                📦 PACKAGE & IMPORTS:
                • Use package: com.ezone.repository
                • Import required classes: org.springframework.data.jpa.repository.JpaRepository, org.springframework.stereotype.Repository, java.util.List, java.util.Optional
                • Add @Repository annotation to each interface

                🏗️ INTERFACE STRUCTURE:
                • Each repository MUST extend JpaRepository<EntityName, IdType>
                • Interface name format: EntityNameRepository (e.g., CartRepository, ProductRepository)
                • Infer Entity name from method return types (Cart → CartRepository)
                • Infer ID type from method parameters (int id → Integer, long id → Long)

                🔄 METHOD CONVERSION RULES:

                A. DO NOT REDECLARE these methods (already in JpaRepository):
                ❌ GetAllAsync() → findAll() [BUILT-IN]
                ❌ GetByIdAsync(int id) → findById(Integer id) [BUILT-IN]
                ❌ AddAsync(Entity e) → save(Entity e) [BUILT-IN]
                ❌ UpdateAsync(Entity e) → save(Entity e) [BUILT-IN]
                ❌ DeleteAsync(int id) → deleteById(Integer id) [BUILT-IN]

                B. CONVERT these to Spring Data JPA derived query methods:
                ✅ GetByUserAsync(int userId) → List<Entity> findByUserId(Integer userId);
                ✅ GetByUsernameAsync(string username) → Optional<Entity> findByUsername(String username);
                ✅ GetCartForUserAsync(int userId) → List<Cart> findByUserId(Integer userId);
                ✅ GetByUserAsync(int userId) → List<Order> findByUserId(Integer userId);

                C. CUSTOM METHODS (require @Query or custom implementation):
                ✅ ClearCartAsync(int userId) → void deleteByUserId(Integer userId);
                ✅ RemoveAsync(int cartItemId) → void deleteById(Integer cartItemId); [BUILT-IN, don't redeclare]
                ✅ AddOrUpdateAsync(Cart item) → Cart save(Cart cart); [BUILT-IN, don't redeclare]

                D. METHOD NAMING CONVENTIONS:
                • Use Spring Data JPA keywords: findBy, deleteBy, countBy, existsBy
                • Property names must match Entity field names exactly (userId → findByUserId)
                • Return types:
                    - Single entity → Optional<Entity> (for nullable results)
                    - Collections → List<Entity>
                    - Delete operations → void
                    - Save operations → Entity (return saved entity)

                🎯 TYPE CONVERSIONS:
                • Task<Entity> → Optional<Entity> (for single results that might not exist)
                • Task<Entity> → Entity (for operations that always return, like save)
                • Task<IEnumerable<Entity>> → List<Entity>
                • Task<bool> → void (for delete operations)
                • int/long parameters → Integer/Long (use wrapper classes)
                • string → String

                ⚠️ SPECIAL CASES:
                • CreateAsync(Order order) → Order save(Order order); [BUILT-IN, don't redeclare]
                • AddOrUpdateAsync(Entity) → Entity save(Entity entity); [BUILT-IN, don't redeclare]
                • Methods returning bool → convert to void for delete operations
                • Async suffix → remove entirely (Spring Data JPA is synchronous by default)

                📋 OUTPUT REQUIREMENTS:
                ✓ Generate ONE repository interface per input interface
                ✓ Use Java naming conventions (camelCase for methods, PascalCase for classes)
                ✓ Include package declaration and necessary imports
                ✓ Add @Repository annotation
                ✓ ONLY include methods NOT provided by JpaRepository
                ✓ Output ONLY valid Java code - NO explanations, NO comments, NO markdown
                ✓ No text before or after the code
                ✓ Ensure proper semicolons and Java syntax

                🚫 WHAT NOT TO DO:
                ✗ Do NOT use @Query annotations unless absolutely necessary
                ✗ Do NOT create implementation classes
                ✗ Do NOT include CRUD methods (save, findById, findAll, deleteById)
                ✗ Do NOT add comments or explanations in the output
                ✗ Do NOT merge multiple repositories into one
                ✗ Do NOT include methods that JpaRepository already provides

                ═══════════════════════════════════════════════════════════════════════════════
                INPUT .NET REPOSITORY INTERFACE(S):
                ═══════════════════════════════════════════════════════════════════════════════

                {dotnet_code}

                ═══════════════════════════════════════════════════════════════════════════════
                GENERATE JAVA SPRING BOOT REPOSITORY CODE BELOW (CODE ONLY, NO EXPLANATIONS):
                ═══════════════════════════════════════════════════════════════════════════════
                """
                elif file.endswith('Service.cs'):
                    # Implementation -> ServiceImpl
                    base_name = file[:-3] # "CartService"
                    java_filename = f"{base_name}Impl.java"
                    folder_name = "Service"
                    prompt = f"""You are a senior Java Spring Boot developer with strong experience in migrating .NET applications.

                    Convert the following .NET Business / Service IMPLEMENTATION class into an equivalent Java Spring Boot SERVICE IMPLEMENTATION class.

                    STRICT RULES:
                    1. Output ONLY Java code. No explanations.
                    2. Create ONLY service IMPLEMENTATION classes.
                    3. Annotate the class with @Service.
                    4. Implement the corresponding Java service interface (assume it already exists).
                    5. Use constructor-based dependency injection (no field injection).
                    6. Replace async/await with synchronous Java code.
                    7. Convert Task<T> to T and Task<IEnumerable<T>> to List<T>.
                    8. Use Spring Data JPA repositories (assume they already exist).
                    9. Do NOT write database queries manually.
                    10. Do NOT include repository interfaces or entity definitions.
                    11. Preserve all business logic exactly (calculations, validations, orchestration).
                    12. Replace LINQ operations with Java Streams.
                    13. Replace Newtonsoft.Json serialization with Jackson ObjectMapper.
                    14. Use @Transactional where multiple database operations occur.
                    15. Use java.util.List and java.math.BigDecimal where appropriate.
                    16. Use Java naming conventions.
                    17. Use package name: com.ezone.service.impl.
                    18. One service class per file.

                    OUTPUT FORMAT:
                    - One Java class per file.
                    - Return ONLY Java code.
                    
                    Input Code:
                    {dotnet_code}"""

            # 3. Models
            elif 'Models' in relative_path:
                java_filename = file.replace('.cs', '.java')
                folder_name = "Model"
                prompt = f"""You are an expert Java Spring Boot developer.

                Convert the following .NET EF Core model classes into equivalent Java Spring Boot JPA entity classes.

                RULES:
                1. Use Jakarta Persistence (jakarta.persistence.*) annotations.
                2. Use @Entity and @Table.
                3. Map [Key] to @Id and @GeneratedValue(strategy = GenerationType.IDENTITY).
                4. Map [Required] to @Column(nullable = false).
                5. Convert DateTime to java.time.LocalDateTime.
                6. Preserve default values using field initialization.
                7. Keep JSON stored fields as String.
                8. Convert nullable C# fields to nullable Java fields.
                9. Do NOT include repository, service, or controller code.
                10. Do NOT add business logic.
                11. Use Lombok annotations (@Getter, @Setter, @NoArgsConstructor, @AllArgsConstructor) to reduce boilerplate.
                12. Convert IdentityUser inheritance into a standalone User entity with username, email, password fields.
                13. Use Java naming conventions.
                14. Each class must be in its own file.

                OUTPUT FORMAT:
                - Return ONLY Java code.
                - One entity per file.
                - No explanations.

                Context from AppDbContext (Use this to determine relationships and strict mappings):
                {context['AppDbContext']}
                
                Input Model Code:
                {dotnet_code}"""

            # 4. Controllers
            elif 'Controllers' in relative_path:
                 java_filename = file.replace('.cs', '.java')
                 folder_name = "Controller"
                 prompt = f"""Convert this .NET Controller to a Spring Boot @RestController.
                 Rules:
                 1. Use @RestController, @RequestMapping.
                 2. Return only Java code.
                 
                 Input Code:
                 {dotnet_code}"""

            # 5. Config / Main (Program.cs)
            elif file == 'Program.cs' and not processed_program:
                processed_program = True
                # We need to generate roughly 3 files from this: Main App, SecurityConfig, WebConfig.
                # Since the loop handles one file at a time, we will make a combined prompt or yield multiple files?
                # The generator yields one result per "file" in the loop. 
                # Strategy: Make 3 separate API calls here and write 3 files.
                
                # A. Main Application
                prompt_main = f"""Create the Main Spring Boot Application class (EZoneApplication.java) from this Program.cs.
                Rules:
                1. @SpringBootApplication.
                2. main method.
                
                Input Program.cs:
                {dotnet_code}"""
                
                # B. Security Config
                prompt_security = f"""Create a Spring Security Configuration (SecurityConfig.java) from this Program.cs.
                Rules:
                1. @Configuration, @EnableWebSecurity.
                2. Configure JWT if present in input.
                3. Configure CORS if present.
                
                Input Program.cs:
                {dotnet_code}"""
                
                # C. Web Config / CORS
                prompt_web = f"""Create a Web Configuration (WebConfig.java) for CORS from this Program.cs.
                Rules:
                1. @Configuration, WebMvcConfigurer.
                
                Input Program.cs:
                {dotnet_code}"""
                
                # Execute generation for Main App
                try:
                    model = genai.GenerativeModel("gemma-3-27b-it")
                    resp_main = model.generate_content(prompt_main)
                    resp_sec = model.generate_content(prompt_security)
                    resp_web = model.generate_content(prompt_web)
                    
                    # Helper to write and yield
                    def write_and_yield(content, fname, folder="Config"):
                        cleaned = content.strip().replace('```java', '').replace('```', '').strip()
                        out_dir = os.path.join(output_folder, folder)
                        os.makedirs(out_dir, exist_ok=True)
                        out_path = os.path.join(out_dir, fname)
                        with open(out_path, 'w', encoding='utf-8') as f: f.write(cleaned)
                        print(f"Generated {fname}")
                        yield {'type': 'file', 'data': {'name': fname, 'path': 'Config/' + fname, 'convertedCode': cleaned}}

                    # We have to yield from inside the generator.
                    # This is tricky because we are inside a loop over files.
                    # Only yield one result per loop iteration usually? No, we can yield multiple times.
                    
                    # Main App (root)
                    yield from write_and_yield(resp_main.text, "EZoneApplication.java", "")
                    # Security
                    yield from write_and_yield(resp_sec.text, "SecurityConfig.java", "Config")
                    # Web
                    yield from write_and_yield(resp_web.text, "WebConfig.java", "Config")
                    
                    continue # Skip normal processing for this file
                    
                except Exception as e:
                     print(f"Error converting Program.cs: {e}")
                     continue

            # 6. Appsettings
            elif file == 'appsettings.json':
                java_filename = 'application.properties'
                folder_name = ""
                prompt = f"""Convert .NET appsettings.json to application.properties.
                Rules:
                1. Convert connection strings.
                2. Convert logging settings.
                
                Input:
                {dotnet_code}"""

            # 7. Dependencies (cspro -> pom.xml)
            elif file.endswith('.csproj'):
                 java_filename = "pom.xml"
                 folder_name = ""
                 prompt = f"""Create a Maven pom.xml for a Spring Boot application based on this .NET csproj.
                 Rules:
                 1. Add dependencies equivalent to the NuGet packages used.
                 2. Use Spring Boot Starter Web, Data JPA, Security.
                 3. Use Lombok, MySQL/PostgreSQL driver (infer from context or use generic).
                 
                 Input .csproj:
                 {dotnet_code}"""

            else:
                # Other .cs files or unknown types -> Skip or generic
                continue

            # --- Execute API Call for Standard Files ---
            if prompt and java_filename:
                model = genai.GenerativeModel("gemma-3-27b-it")
                response = model.generate_content(prompt)
                
                cleaned_text = response.text.strip().replace('```java', '').replace('```xml', '').replace('```properties','').replace('```', '').strip()
                
                # Determine output path
                if folder_name:
                    out_dir = os.path.join(output_folder, folder_name)
                else:
                    out_dir = output_folder
                
                os.makedirs(out_dir, exist_ok=True)
                output_path = os.path.join(out_dir, java_filename)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_text)
                
                print(f"Converted: {relative_path} -> {java_filename}")
                yield {
                    'type': 'file',
                    'data': {
                        'name': java_filename,
                        'path': relative_path,
                        'originalCode': dotnet_code,
                        'convertedCode': cleaned_text
                    }
                }

        except Exception as e:
            print(f"Error converting {file}: {e}")
            yield {'type': 'error', 'message': f"Error converting {file}: {str(e)}"}
    
    # Create zip logic remains...
    zip_output_path = f"{output_folder}.zip"
    with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_folder)
                zipf.write(file_path, arcname)
    
    yield {
        'type': 'complete',
        'zip_path': zip_output_path
    }

if __name__ == "__main__":
    zip_file = input("Enter .NET Web API zip file path: ")
    extract_folder = "temp_extract"
    output_folder = "springboot_output6"
    
    unzip_and_convert(zip_file, extract_folder, output_folder)
    print(f"Conversion complete! Check {output_folder} folder and {output_folder}.zip file")