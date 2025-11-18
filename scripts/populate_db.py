import os
import csv
import psycopg2
import time
import random
import re
import sys

# List of colors for random first names, as one was not provided
COLORS = [
    "Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Black", "White",
    "Pink", "Brown", "Gray", "Cyan", "Magenta", "Teal", "Navy", "Olive",
    "Maroon", "Lime", "Aqua", "Silver"
]

# List of animals for random last names, as provided
ANIMALS = [
    "alligator", "anteater", "armadillo", "auroch", "axolotl", "badger", "bat",
    "bear", "beaver", "blobfish", "buffalo", "camel", "chameleon", "cheetah",
    "chipmunk", "chinchilla", "chupacabra", "cormorant", "coyote", "crow",
    "dingo", "dinosaur", "dog", "dolphin", "dragon", "duck", "dumbo octopus",
    "elephant", "ferret", "fox", "frog", "giraffe", "goose", "gopher",
    "grizzly", "hamster", "hedgehog", "hippo", "hyena", "jackal", "jackalope",
    "ibex", "ifrit", "iguana", "kangaroo", "kiwi", "koala", "kraken", "lemur",
    "leopard", "liger", "lion", "llama", "manatee", "mink", "monkey", "moose",
    "narwhal", "nyan cat", "orangutan", "otter", "panda", "penguin",
    "platypus", "python", "pumpkin", "quagga", "quokka", "rabbit", "raccoon",
    "rhino", "sheep", "shrew", "skunk", "slow loris", "squirrel", "tiger",
    "turtle", "unicorn", "walrus", "wolf", "wolverine", "wombat",
]


def get_db_connection():
    """Establishes a connection to the database with retries."""
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host="db"
            )
            print("Successfully connected to the database.")
            return conn
        except psycopg2.OperationalError as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            retries -= 1
            time.sleep(5)

    print("Could not connect to the database after 5 attempts.", file=sys.stderr)
    raise Exception("Database connection failed")


def populate_carriers(cur):
    """Populates the carriers table from package_data.csv."""
    print("Populating carriers table...")
    carriers = set()
    try:
        with open('package_data.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                carrier_name = row.get('Carrier')
                if carrier_name:
                    carriers.add(carrier_name)

        insert_sql = """
        INSERT INTO carriers (carrier_name) VALUES (%s)
        ON CONFLICT (carrier_name) DO NOTHING;
        """

        for carrier_name in carriers:
            cur.execute(insert_sql, (carrier_name,))

        print(f"Populated/updated {len(carriers)} carriers.")

    except Exception as e:
        print(f"Error populating carriers: {e}", file=sys.stderr)
        raise


def populate_emissions(cur):
    """Populates the emissions table from emissions_data.csv."""
    print("Populating emissions table...")
    services = {}
    try:
        with open('emissions_data.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only add if service AND factor are valid
                service = row.get('service')
                factor = row.get('emission_factor')
                if service and factor:  # This skips None, '', etc.
                    try:
                        # Keep the first factor found for a given service
                        if service not in services:
                            services[service] = float(factor)
                    except ValueError:
                        pass  # Ignore rows with invalid emission_factor

        insert_sql = """
        INSERT INTO emissions (service_type, emission_factor) VALUES (%s, %s)
        ON CONFLICT (service_type) DO NOTHING;
        """

        for service, factor in services.items():
            cur.execute(insert_sql, (service, factor))

        print(f"Populated {len(services)} emission service types.")

    except Exception as e:
        print(f"Error populating emissions: {e}", file=sys.stderr)
        raise


def populate_persons(cur):
    """Populates the persons and departments tables from package_data.csv."""
    print("Populating persons and departments tables...")
    persons = {}
    
    # Realistic WPI Departments
    DEPARTMENTS = [
        "Computer Science", "Robotics Engineering", "Mechanical Engineering",
        "Electrical & Computer Engineering", "Biomedical Engineering",
        "Chemical Engineering", "Civil & Environmental Engineering",
        "Aerospace Engineering", "Interactive Media & Game Development",
        "Mathematical Sciences", "Physics", "Chemistry & Biochemistry",
        "Biology & Biotechnology", "Humanities & Arts", "Social Science & Policy Studies",
        "Business", "Fire Protection Engineering"
    ]
    
    CLASS_YEARS = [2026, 2027, 2028, 2029]

    try:
        # First pass: Count packages per person to influence class year
        package_counts = {}
        with open('package_data.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                location_1 = row.get('Location 1')
                if location_1 and re.match(r'^\d{4}$', location_1):
                    wpi_id = location_1.zfill(9)
                    package_counts[wpi_id] = package_counts.get(wpi_id, 0) + 1

        # Second pass: Generate person data
        with open('package_data.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                location_1 = row.get('Location 1')
                if location_1 and re.match(r'^\d{4}$', location_1):
                    wpi_id = location_1.zfill(9)
                    if wpi_id not in persons:
                        # Determine class year based on package count
                        # Logic: Higher package count -> Higher probability of being Freshmen (2029)
                        # We'll use weights. Base weight 1.
                        # Bonus weight for 2029 based on package count.
                        count = package_counts.get(wpi_id, 0)
                        
                        # Weights for [2026, 2027, 2028, 2029]
                        # 2029 gets a boost proportional to package count
                        # Example: if count is 0, weight is 1. If count is 10, weight is 6.
                        w_2029 = 1 + (count * 0.5) 
                        weights = [1, 1, 1, w_2029]
                        
                        class_year = random.choices(CLASS_YEARS, weights=weights, k=1)[0]
                        
                        persons[wpi_id] = {
                            "box_number": location_1,
                            "first_name": random.choice(COLORS),
                            "last_name": random.choice(ANIMALS).capitalize(),
                            "class_year": class_year,
                            "department": random.choice(DEPARTMENTS)
                        }

        insert_person_sql = """
        INSERT INTO persons (wpi_id, first_name, last_name, is_student, is_mailroom_worker, box_number, class_year, supervisor_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL)
        ON CONFLICT (wpi_id) DO NOTHING;
        """
        
        insert_dept_sql = """
        INSERT INTO departments (person_id, department_name)
        VALUES (%s, %s)
        ON CONFLICT (person_id, department_name) DO NOTHING;
        """

        for wpi_id, data in persons.items():
            # Insert Person
            cur.execute(insert_person_sql, (
                wpi_id,
                data['first_name'],
                data['last_name'],
                True,  # is_student
                False,  # is_mailroom_worker
                data['box_number'],
                data['class_year']
            ))
            
            # Insert Department
            cur.execute(insert_dept_sql, (
                wpi_id,
                data['department']
            ))

        print(f"Populated {len(persons)} persons and their departments.")

    except Exception as e:
        print(f"Error populating persons: {e}", file=sys.stderr)
        raise


def populate_packages(cur):
    """Populates the packages table using data from both CSV files."""
    print("Populating packages table...")

    # 1. Get carrier IDs from DB
    cur.execute("SELECT carrier_id, carrier_name FROM carriers;")
    carrier_map = {name: id for id, name in cur.fetchall()}

    # 2. Load emissions data into a dictionary for quick lookup
    emissions_data = {}
    try:
        with open('emissions_data.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tracking_num = row.get('tracking_number')
                if tracking_num:
                    emissions_data[tracking_num] = {
                        "service": row.get('service'),
                        "emissions_kg": row.get('total_emissions_kg_co2e'),
                        # --- THIS IS THE FIX ---
                        "distance_km": row.get('distance_km')
                        # --- END OF FIX ---
                    }
    except Exception as e:
        print(f"Error reading emissions_data.csv: {e}", file=sys.stderr)
        raise

    print(f"Loaded {len(emissions_data)} emissions records into memory.")

    # 3. Read package_data.csv and insert into packages table
    packages_to_insert = []
    try:
        with open('package_data.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                location_1 = row.get('Location 1')
                # Only process packages with a valid recipient (4-digit box number)
                if not (location_1 and re.match(r'^\d{4}$', location_1)):
                    continue

                recipient_id = location_1.zfill(9)  # Pad to 9 chars
                tracking_num_raw = row.get('Tracking #')

                # Remove trailing underscore
                tracking_num = tracking_num_raw.rstrip('_') if tracking_num_raw else None

                if not tracking_num:
                    continue

                carrier_name = row.get('Carrier')
                carrier_id = carrier_map.get(carrier_name)  # Get FK

                # Get data from emissions dict
                em_data = emissions_data.get(tracking_num)

                if em_data:
                    # If service is '' or None, set to NULL (None)
                    service_type = em_data['service']
                    if not service_type:
                        service_type = None

                    try:
                        total_emissions = float(em_data['emissions_kg'])
                    except (ValueError, TypeError):
                        total_emissions = None
                    try:
                        distance = float(em_data['distance_km'])
                    except (ValueError, TypeError):
                        distance = None
                else:
                    # No emissions data found for this tracking number
                    service_type = None
                    total_emissions = None
                    distance = None

                # As discovered, date_shipped is not available. Set to NULL.
                date_shipped = row.get('Delivered Date Time')
                # Convert date_shipped from 10/29/25 10:55 to 2025-10-29 10:55:00
                if date_shipped:
                    try:
                        date_shipped = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.strptime(date_shipped, "%m/%d/%y %H:%M")
                        )
                    except ValueError:
                        date_shipped = None
                else:
                    date_shipped = None

                packages_to_insert.append((
                    carrier_id,
                    recipient_id,
                    tracking_num,
                    service_type,
                    date_shipped,
                    total_emissions,
                    distance
                ))

        insert_sql = """
        INSERT INTO packages (
            carrier_id, recipient_id, tracking_number, service_type, 
            date_shipped, total_emissions_kg, distance_traveled
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tracking_number) DO NOTHING;
        """

        count = 0
        failed_fk = 0

        # We must handle errors on each execute
        for package_data in packages_to_insert:
            try:
                cur.execute(insert_sql, package_data)
                count += 1
            except psycopg2.Error as e:
                # This catches the error (like FK violation)
                # and ROLLS BACK the single failed statement
                # so the transaction can continue.
                cur.execute("ROLLBACK TO SAVEPOINT packages_loop")

                if e.pgcode == '23503':  # foreign_key_violation
                    failed_fk += 1
                else:
                    print(f"Skipping package {package_data[2]} due to error: {e}")

        print(f"Attempted to insert {len(packages_to_insert)} packages.")
        print(f"Successfully processed {count} package insertions.")
        if failed_fk > 0:
            print(f"Skipped {failed_fk} packages due to Foreign Key violations (e.g., service not in emissions table).")


    except Exception as e:
        print(f"Error populating packages: {e}", file=sys.stderr)
        raise


def populate_db():
    conn = None
    cur = None  # Define cur here so it's in scope for finally
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Populate in correct order to respect foreign key constraints

        # 1. carriers (no dependencies)
        populate_carriers(cur)
        conn.commit()

        # 2. emissions (no dependencies)
        populate_emissions(cur)
        conn.commit()

        # 3. persons and departments (no dependencies)
        populate_persons(cur)
        conn.commit()

        # 4. packages (depends on carriers, persons, emissions)

        # Create a savepoint for the package loop
        # This allows us to roll back *individual* failed inserts
        # without aborting the whole transaction
        cur.execute("SAVEPOINT packages_loop")

        populate_packages(cur)
        conn.commit()

        print("\nDatabase population complete!")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        if conn:
            conn.rollback()  # Roll back changes on error
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    populate_db()
