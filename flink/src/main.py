import logging, sys

from pyflink.common import Row
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import Schema, DataTypes, TableDescriptor, StreamTableEnvironment
from pyflink.table.expressions import col, row
from pyflink.table.udf import ACC, T, udaf, AggregateFunction, udf

logging.basicConfig(stream=sys.stdout, level=logging.ERROR, format="%(message)s")


class EmitLastState(AggregateFunction):
    """
    Aggregator that emits the latest state for the purpose of
    enabling parallelism on CDC tables.
    """

    def create_accumulator(self) -> ACC:
        return Row(None, None)

    def accumulate(self, accumulator: ACC, *args):
        key, obj = args
        if (accumulator[0] is None) or (key > accumulator[0]):
            accumulator[0] = key
            accumulator[1] = obj

    def retract(self, accumulator: ACC, *args):
        pass

    def get_value(self, accumulator: ACC) -> T:
        return accumulator[1]


some_complex_inner_type = DataTypes.ROW(
    [
        DataTypes.FIELD("f0", DataTypes.STRING()),
        DataTypes.FIELD("f1", DataTypes.STRING())
    ]
)

some_complex_type = DataTypes.ROW(
    [
        DataTypes.FIELD(k, DataTypes.ARRAY(some_complex_inner_type))
        for k in ("f0", "f1", "f2")
    ]
    + [
        DataTypes.FIELD("f3", DataTypes.DATE()),
        DataTypes.FIELD("f4", DataTypes.VARCHAR(32)),
        DataTypes.FIELD("f5", DataTypes.VARCHAR(2)),
    ]
)

@udf(input_types=DataTypes.STRING(), result_type=some_complex_type)
def complex_udf(s):
    return Row(f0=None, f1=None, f2=None, f3=None, f4=None, f5=None)


if __name__ == "__main__":
    env = StreamExecutionEnvironment.get_execution_environment()
    table_env = StreamTableEnvironment.create(env)

    # Create schema
    _schema = {
        "p_key": DataTypes.INT(False),
        "modified_id": DataTypes.INT(False),
        "content": DataTypes.STRING()
    }
    schema = Schema.new_builder().from_fields(
        *zip(*[(k, v) for k, v in _schema.items()])
    ).\
        primary_key("p_key").\
        build()

    # Create table descriptor
    descriptor = TableDescriptor.for_connector("postgres-cdc").\
        option("hostname", "host.docker.internal").\
        option("port", "5432").\
        option("database-name", "flink_issue").\
        option("username", "root").\
        option("password", "root").\
        option("debezium.plugin.name", "pgoutput").\
        option("schema-name", "flink_schema").\
        option("table-name", "flink_table").\
        option("slot.name", "flink_slot").\
        schema(schema).\
        build()

    table_env.create_temporary_table("flink_table", descriptor)

    # Create changelog stream
    stream = table_env.from_path("flink_table")\

    # Define UDAF
    accumulator_type = DataTypes.ROW(
        [
            DataTypes.FIELD("f0", DataTypes.INT(False)),
            DataTypes.FIELD("f1", DataTypes.ROW([DataTypes.FIELD(k, v) for k, v in _schema.items()])),
        ]
    )
    result_type = DataTypes.ROW([DataTypes.FIELD(k, v) for k, v in _schema.items()])
    emit_last = udaf(EmitLastState(), accumulator_type=accumulator_type, result_type=result_type)

    # Emit last state based on modified_id to enable parallel processing
    stream = stream.\
        group_by(col("p_key")).\
        select(
        col("p_key"),
        emit_last(col("modified_id"),row(*(col(k) for k in _schema.keys())).cast(result_type)).alias("tmp_obj")
    )

    # Select the elements of the objects
    stream = stream.select(*(col("tmp_obj").get(k).alias(k) for k in _schema.keys()))

    # We apply a UDF which parses the xml and returns a complex nested structure
    stream = stream.select(col("p_key"), complex_udf(col("content")).alias("nested_obj"))

    # We select an element from the nested structure in order to flatten it
    # The next line is the line causing issues, commenting the next line will make the pipeline work
    stream = stream.select(col("p_key"), col("nested_obj").get("f0"))

    # Interestingly, the below part does work...
    # stream = stream.select(col("nested_obj").get("f0"))

    table_env.to_changelog_stream(stream).print()

    # Execute
    env.execute_async()
